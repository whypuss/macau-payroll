"""完整薪金計算: 出勤/輪更/請假 -> 實發工資。

計算順序:
  應稅工資 = 月薪 + 夜更津貼 + 加班費
             - 無薪假扣款 - 缺勤扣款 - 無證病假扣款 - 遲到扣款
             - 超額年假扣款 (年假超出額度部份, 當無薪假計)
  稅款     = monthly_withholding(應稅工資)   (沿用 payroll.py 職業稅)
  實發     = 應稅工資 - 稅款 - 社保僱員供款 (MOP 30/月, 稅後代扣)

社保 (社會保障基金強制性制度, 第4/2010號法律):
  僱主 MOP 60/月/人 (公司成本, 不扣員工), 僱員 MOP 30/月/人 (稅後代扣)。
  僱員供款在本 skill 不扣減應稅工資 (是否可扣減應課稅收益, 需會計核實)。
  勞動關係開始/終止月份工作少於 15 日該月無須供款 (模擬中全部全月在職)。

年假 / 有證病假: 額度內全薪不扣。
"""
from payroll import monthly_withholding

NIGHT_ALLOWANCE = 80.0   # MOP / 更
LATE_GRACE_MIN = 5.0     # 遲到寬限分鐘
OVERTIME_MULT = 1.5      # 加班倍率
FSS_EMPLOYEE = 30.0      # 社保僱員供款 MOP/月 (稅後代扣)
FSS_EMPLOYER = 60.0      # 社保僱主供款 MOP/月 (公司成本)


def compute_payslip(emp, records):
    monthly = float(emp["monthly_salary"])
    daily = monthly / 30.0
    hourly = daily / 8.0

    night_shifts = sum(1 for r in records
                       if r["type"] == "work" and r["shift"] == "夜")
    allowance = round(night_shifts * NIGHT_ALLOWANCE, 2)

    ot_hours = round(sum(r["ot_hours"] for r in records if r["type"] == "work"), 2)
    ot_pay = round(ot_hours * hourly * OVERTIME_MULT, 2)

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
                               for r in records if r["type"] == "work"), 1)
    late_ded = round(late_min_total * hourly / 60.0, 2)

    deductions = round(nopay_ded + absent_ded + sick_ded + late_ded, 2)
    taxable = round(max(0.0, monthly + allowance + ot_pay - deductions), 2)
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
        "total_deductions": round(sum(s["deductions"]["total"] for s in slips), 2),
        "total_fss_employee": round(sum(s["social_security_employee"] for s in slips), 2),
        "total_fss_employer": round(sum(s["social_security_employer"] for s in slips), 2),
    }
    return slips, totals
