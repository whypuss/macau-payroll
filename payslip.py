"""完整薪金計算: 出勤/輪更/請假 -> 實發工資。

計算順序:
  應稅工資 = 月薪 + 夜更津貼 + 加班費
             + 強制性假日工作額外報酬 + 週假工作額外報酬
             + 颱風工作額外報酬 + 颱風津貼
             - 無薪假扣款 - 缺勤扣款 - 無證病假扣款 - 遲到扣款
             - 超額年假扣款 (年假超出額度部份, 當無薪假計)
  稅款     = monthly_withholding(應稅工資)   (沿用 payroll.py 職業稅)
  實發     = 應稅工資 - 稅款 - 社保僱員供款 (MOP 30/月, 稅後代扣)

法定假日工作 (第7/2008號法律《勞動關係法》):
  強制性假日工作 = 三工: 月薪已含當日 1 工, 額外 2× 日基本報酬;
    僱員可選擇其中 1 工轉為工作後 30 日內有薪補假 (comp_leave=True)。
  週假工作 = 雙工: 月薪已含當日 1 工, 額外 1× 日基本報酬;
    或選擇工作後 30 日內有薪補休 1 日代替額外報酬 (comp_leave=True)。
  基本報酬 = 月薪 / 30。
颱風: 《勞動關係法》無強制規定, 勞工局《颱風及突發公共事件下之工作指引》
  僅屬參考性質; 報酬由勞資預先書面協商。本 skill 以公司政策參數計:
  颱風工作額外報酬 = 日薪 × TYPHOON_EXTRA_MULT, 另加定額颱風津貼。
  颱風停工唔返工不扣薪 (無需特別記錄)。

社保 (社會保障基金強制性制度, 第4/2010號法律):
  僱主 MOP 60/月/人 (公司成本, 不扣員工), 僱員 MOP 30/月/人 (稅後代扣)。
  僱員供款在本 skill 不扣減應稅工資 (是否可扣減應課稅收益, 需會計核實)。
  勞動關係開始/終止月份工作少於 15 日該月無須供款 (模擬中全部全月在職)。

年假 / 有證病假 / 補假: 額度內全薪不扣。
"""
from payroll import monthly_withholding

NIGHT_ALLOWANCE = 80.0   # MOP / 更
LATE_GRACE_MIN = 5.0     # 遲到寬限分鐘
OVERTIME_MULT = 1.5      # 加班倍率
FSS_EMPLOYEE = 30.0      # 社保僱員供款 MOP/月 (稅後代扣)
FSS_EMPLOYER = 60.0      # 社保僱主供款 MOP/月 (公司成本)

# --- 法定假日工作倍數 ---
HOLIDAY_EXTRA_MULT = 2.0  # 強制性假日工作: 額外 2× 日基本報酬 (三工)
RESTDAY_EXTRA_MULT = 1.0  # 週假工作: 額外 1× 日基本報酬 (雙工)
# --- 公司政策 (颱風; 須按公司實際政策調整) ---
TYPHOON_EXTRA_MULT = 1.0  # 颱風期間工作: 額外 1× 日薪 (預設雙工總額)
TYPHOON_ALLOWANCE = 0.0    # 颱風津貼 MOP/日 (定額)

# 計夜更 / 加班 / 遲到嘅工作記錄類型
WORK_TYPES = ("work", "holiday_work", "restday_work", "typhoon_work")


def compute_payslip(emp, records):
    monthly = float(emp["monthly_salary"])
    daily = monthly / 30.0
    hourly = daily / 8.0

    night_shifts = sum(1 for r in records
                       if r["type"] in WORK_TYPES and r["shift"] == "夜")
    allowance = round(night_shifts * NIGHT_ALLOWANCE, 2)

    ot_hours = round(sum(r["ot_hours"] for r in records
                         if r["type"] in WORK_TYPES), 2)
    ot_pay = round(ot_hours * hourly * OVERTIME_MULT, 2)

    # 法定假日工作: comp_leave=True 表示僱員選擇其中 1 工轉有薪補假
    holiday_recs = [r for r in records if r["type"] == "holiday_work"]
    restday_recs = [r for r in records if r["type"] == "restday_work"]
    typhoon_recs = [r for r in records if r["type"] == "typhoon_work"]
    holiday_days = len(holiday_recs)
    restday_days = len(restday_recs)
    typhoon_days = len(typhoon_recs)
    holiday_extra = round(sum(
        daily * (HOLIDAY_EXTRA_MULT - (1.0 if r.get("comp_leave") else 0.0))
        for r in holiday_recs), 2)
    restday_extra = round(sum(
        daily * (RESTDAY_EXTRA_MULT - (1.0 if r.get("comp_leave") else 0.0))
        for r in restday_recs), 2)
    typhoon_extra = round(typhoon_days * daily * TYPHOON_EXTRA_MULT, 2)
    typhoon_allow = round(typhoon_days * TYPHOON_ALLOWANCE, 2)
    comp_leave_days = sum(1 for r in records if r["type"] == "comp_leave")
    comp_leave_owed = max(0, sum(1 for r in holiday_recs + restday_recs
                                 if r.get("comp_leave")) - comp_leave_days)

    nopay_days = sum(1 for r in records if r["type"] == "nopay")
    absent_days = sum(1 for r in records if r["type"] == "absent")
    sick_uncert_days = sum(1 for r in records
                           if r["type"] == "sick" and not r["cert"])
    annual_days = sum(1 for r in records if r["type"] == "annual")
    sick_cert_days = sum(1 for r in records
                         if r["type"] == "sick" and r["cert"])

    # 年假額度: 跟 join date / 職位 / 特殊加額; 超出部份當無薪假扣
    entitlement = int(emp.get("annual_leave_entitlement", 12))
    excess_annual = max(0, annual_days - entitlement)
    annual_remaining = max(0, entitlement - annual_days)

    nopay_ded = round((nopay_days + excess_annual) * daily, 2)
    absent_ded = round(absent_days * daily, 2)
    sick_ded = round(sick_uncert_days * daily, 2)
    late_min_total = round(sum(max(0.0, r["late_min"] - LATE_GRACE_MIN)
                               for r in records if r["type"] in WORK_TYPES), 1)
    late_ded = round(late_min_total * hourly / 60.0, 2)

    deductions = round(nopay_ded + absent_ded + sick_ded + late_ded, 2)
    extras = round(allowance + ot_pay + holiday_extra + restday_extra
                   + typhoon_extra + typhoon_allow, 2)
    taxable = round(max(0.0, monthly + extras - deductions), 2)
    tax = monthly_withholding(taxable)["monthly_tax_withheld"]
    net = round(max(0.0, taxable - tax - FSS_EMPLOYEE), 2)

    return {
        "id": emp["id"], "name": emp["name"], "role": emp["role"],
        "monthly_salary": round(monthly, 2),
        "daily_rate": round(daily, 2),
        "night_shifts": night_shifts,
        "night_allowance": allowance,
        "ot_hours": ot_hours,
        "overtime_pay": ot_pay,
        "holiday_work_days": holiday_days,
        "holiday_work_extra": holiday_extra,
        "restday_work_days": restday_days,
        "restday_work_extra": restday_extra,
        "typhoon_work_days": typhoon_days,
        "typhoon_work_extra": typhoon_extra,
        "typhoon_allowance": typhoon_allow,
        "comp_leave_days": comp_leave_days,
        "comp_leave_owed_days": comp_leave_owed,
        "annual_leave_days": annual_days,
        "annual_leave_entitlement": entitlement,
        "annual_leave_excess_days": excess_annual,
        "annual_leave_remaining": annual_remaining,
        "sick_cert_days": sick_cert_days,
        "sick_uncert_days": sick_uncert_days,
        "nopay_days": nopay_days,
        "absent_days": absent_days,
        "late_min_charged": late_min_total,
        "deductions": {
            "nopay": nopay_ded, "absent": absent_ded,
            "sick_uncertified": sick_ded, "late": late_ded,
            "social_security": FSS_EMPLOYEE,
            "total": round(deductions + FSS_EMPLOYEE, 2),
        },
        "social_security_employee": FSS_EMPLOYEE,
        "social_security_employer": FSS_EMPLOYER,
        "taxable_income": taxable,
        "tax_withheld": tax,
        "net_pay": net,
    }


def payroll_run(employees, records):
    """成批計 100 人, 回傳 (payslips, totals)。"""
    slips = [compute_payslip(e, records[e["id"]]) for e in employees]
    totals = {
        "headcount": len(slips),
        "total_taxable": round(sum(s["taxable_income"] for s in slips), 2),
        "total_tax": round(sum(s["tax_withheld"] for s in slips), 2),
        "total_net": round(sum(s["net_pay"] for s in slips), 2),
        "total_night_allowance": round(sum(s["night_allowance"] for s in slips), 2),
        "total_overtime_pay": round(sum(s["overtime_pay"] for s in slips), 2),
        "total_holiday_work_extra": round(sum(s["holiday_work_extra"] for s in slips), 2),
        "total_restday_work_extra": round(sum(s["restday_work_extra"] for s in slips), 2),
        "total_typhoon_work_extra": round(sum(s["typhoon_work_extra"] for s in slips), 2),
        "total_typhoon_allowance": round(sum(s["typhoon_allowance"] for s in slips), 2),
        "total_deductions": round(sum(s["deductions"]["total"] for s in slips), 2),
        "total_fss_employee": round(sum(s["social_security_employee"] for s in slips), 2),
        "total_fss_employer": round(sum(s["social_security_employer"] for s in slips), 2),
    }
    return slips, totals
