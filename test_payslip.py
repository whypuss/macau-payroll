"""完整薪金計算的 tests。

A) 人手個案: 捏造出勤記錄, 預期值全部人手計出。
B) 100 人模擬不變量: 會計恆等式、非負、扣款公式、確定性。
C) 年假額度: 職位基本額、入職當年按比例、超出轉無薪假。
D) 社保供款: 僱員 30 稅後代扣、僱主 60 公司成本。
E) 法定假日工作 / 颱風: 三工、雙工、補假選項、颱風公司政策。
"""
from payslip import compute_payslip, payroll_run
from payroll import monthly_withholding
from simulate import generate


def mkemp(salary, eid="E999", name="測試員", role="職員"):
    return {"id": eid, "name": name, "role": role, "monthly_salary": salary}


def work(shift="早", late=0.0, ot=0.0, day=1):
    return {"date": f"2026-09-{day:02d}", "shift": shift, "type": "work",
            "cert": True, "late_min": late, "ot_hours": ot}


def leave(ltype, day, cert=True):
    return {"date": f"2026-09-{day:02d}", "shift": "早", "type": ltype,
            "cert": cert, "late_min": 0.0, "ot_hours": 0.0}


# ---------- A) 人手個案 ----------

def test_clean_employee():
    # 月薪 25,000, 無假無遲到無加班 → 應稅 25,000 → 稅 828.33 → 實發 24,141.67 (扣社保 30)
    s = compute_payslip(mkemp(25000), [work(day=d) for d in range(1, 5)])
    assert s["taxable_income"] == 25000.0
    assert s["tax_withheld"] == 828.33
    assert s["net_pay"] == 24141.67  # 扣社保 30


def test_nopay_deduction():
    # 月薪 30,000, 1 天無薪假 → 日薪 1,000 → 應稅 29,000
    # 稅: 年化 348,000 → 應課稅 204,000 → 19,440 → 扣減後 13,608 → 月 1,134
    s = compute_payslip(mkemp(30000), [work(day=1), leave("nopay", 2)])
    assert s["nopay_days"] == 1
    assert s["deductions"]["nopay"] == 1000.0
    assert s["taxable_income"] == 29000.0
    assert s["tax_withheld"] == 1134.0
    assert s["net_pay"] == 27836.0


def test_sick_cert_distinction():
    # 月薪 30,000: 2 天有證病假不扣, 1 天無證扣 1,000 → 同上, 實發 27,836
    recs = [work(day=1), leave("sick", 2, cert=True), leave("sick", 3, cert=True),
            leave("sick", 4, cert=False)]
    s = compute_payslip(mkemp(30000), recs)
    assert s["sick_cert_days"] == 2
    assert s["sick_uncert_days"] == 1
    assert s["deductions"]["sick_uncertified"] == 1000.0
    assert s["net_pay"] == 27836.0


def test_night_ot_late_annual():
    # 月薪 24,000 (日薪 800, 時薪 100):
    # 2 夜更 → 津貼 160; 加班 3h → 450; 遲到 10min (扣 5min) → 8.33; 1 天年假不扣
    # 應稅 = 24,000+160+450-8.33 = 24,601.67 → 稅 800.45 → 實發 23,771.22 (扣社保 30)
    recs = [work("早", late=3, day=1), work("夜", late=10, ot=2.0, day=2),
            work("夜", ot=1.0, day=3), leave("annual", 4)]
    s = compute_payslip(mkemp(24000), recs)
    assert s["night_shifts"] == 2
    assert s["night_allowance"] == 160.0
    assert s["ot_hours"] == 3.0
    assert s["overtime_pay"] == 450.0
    assert s["late_min_charged"] == 5.0
    assert s["deductions"]["late"] == 8.33
    assert s["annual_leave_days"] == 1
    assert s["taxable_income"] == 24601.67
    assert s["tax_withheld"] == 800.45
    assert s["net_pay"] == 23771.22


def test_full_month_nopay_zero_net():
    # 全月無薪假 → 實發 0, 稅 0
    s = compute_payslip(mkemp(20000), [leave("nopay", d) for d in range(1, 31)])
    assert s["taxable_income"] == 0.0
    assert s["tax_withheld"] == 0.0
    assert s["net_pay"] == 0.0


# ---------- B) 100 人模擬不變量 ----------

def _run():
    employees, records = generate()
    return payroll_run(employees, records)


def test_headcount():
    slips, totals = _run()
    assert totals["headcount"] == 100
    assert len(slips) == 100


def test_accounting_identity():
    # 實發 + 稅 + 扣款 == 月薪 + 各項津貼/額外報酬 (每人)
    slips, _ = _run()
    for s in slips:
        lhs = round(s["net_pay"] + s["tax_withheld"] + s["deductions"]["total"], 2)
        rhs = round(s["monthly_salary"] + s["night_allowance"]
                    + s["overtime_pay"] + s["holiday_work_extra"]
                    + s["restday_work_extra"] + s["typhoon_work_extra"]
                    + s["typhoon_allowance"], 2)
        assert abs(lhs - rhs) < 0.02, s["id"]


def test_net_non_negative():
    slips, _ = _run()
    assert all(s["net_pay"] >= 0 for s in slips)


def test_deduction_formulas():
    # 無薪假扣款 == 日數 × 日薪(未捨入); 夜更津貼 == 更數 × 80 (每人精確)
    slips, _ = _run()
    for s in slips:
        daily = s["monthly_salary"] / 30.0
        assert s["deductions"]["nopay"] == round(s["nopay_days"] * daily, 2)
        assert s["deductions"]["absent"] == round(s["absent_days"] * daily, 2)
        assert s["night_allowance"] == round(s["night_shifts"] * 80.0, 2)


def test_tax_consistent_with_tax_module():
    # 薪金稅必須同 payroll.py 稅模組一致
    slips, _ = _run()
    for s in slips:
        assert s["tax_withheld"] == monthly_withholding(s["taxable_income"])["monthly_tax_withheld"]


def test_totals_reconcile():
    slips, totals = _run()
    assert abs(totals["total_net"] + totals["total_tax"]
               + totals["total_fss_employee"] - totals["total_taxable"]) < 1.0


def test_simulation_has_variety():
    # 模擬唔可以係死數據: 要有夜更、加班、請假、遲到
    _, totals = _run()
    assert totals["total_night_allowance"] > 0
    assert totals["total_overtime_pay"] > 0
    assert totals["total_deductions"] > 0
    assert totals["total_tax"] > 0


def test_deterministic():
    # 同 seed 生成兩次, 結果完全相同
    slips1, totals1 = _run()
    slips2, totals2 = _run()
    assert totals1 == totals2
    assert [s["net_pay"] for s in slips1] == [s["net_pay"] for s in slips2]


# ---------- C) 年假額度 ----------

def test_annual_entitlement_prorata():
    from datetime import date as ddate
    from simulate import annual_entitlement
    # 職員 base 12, 2026-07 入職 → 12×6/12 = 6
    assert annual_entitlement(ddate(2026, 7, 1), "職員", 0) == 6
    # 助理 base 10, 2026-01 入職 → 足年 10
    assert annual_entitlement(ddate(2026, 1, 1), "助理", 0) == 10
    # 經理 base 15, 舊員工 → 15
    assert annual_entitlement(ddate(2020, 5, 1), "經理", 0) == 15
    # 主任 base 13 + 特殊 3 → 16
    assert annual_entitlement(ddate(2021, 3, 1), "主任", 3) == 16
    # 助理 2026-12 入職 → round(10/12) = 1, 保底 1
    assert annual_entitlement(ddate(2026, 12, 1), "助理", 0) == 1


def test_excess_annual_becomes_nopay():
    # 月薪 30,000, 年假額度 2 天但放咗 4 天 → 超出 2 天當無薪假扣 2,000
    # 應稅 = 28,000 → 年化 336,000 → 應課稅 192,000
    # 1,400+1,600+3,600+8,000+3,520 = 18,120 → 扣減後 12,684 → 月稅 1,057
    emp = mkemp(30000)
    emp["annual_leave_entitlement"] = 2
    recs = [work(day=1)] + [leave("annual", d) for d in range(2, 6)]
    s = compute_payslip(emp, recs)
    assert s["annual_leave_days"] == 4
    assert s["annual_leave_excess_days"] == 2
    assert s["annual_leave_remaining"] == 0
    assert s["deductions"]["nopay"] == 2000.0
    assert s["taxable_income"] == 28000.0
    assert s["tax_withheld"] == 1057.0
    assert s["net_pay"] == 26913.0


def test_simulation_annual_within_entitlement():
    employees, records = generate()
    slips, _ = payroll_run(employees, records)
    for e, s in zip(employees, slips):
        assert s["annual_leave_days"] <= e["annual_leave_entitlement"]
        assert s["annual_leave_remaining"] == \
            e["annual_leave_entitlement"] - s["annual_leave_days"]
        assert s["annual_leave_remaining"] >= 0


def test_simulation_entitlement_formula():
    # 每個員工嘅額度必須同 annual_entitlement 公式一致
    from datetime import date as ddate
    from simulate import annual_entitlement
    employees, _ = generate()
    for e in employees:
        jd = ddate(*map(int, e["join_date"].split("-")))
        assert e["annual_leave_entitlement"] == \
            annual_entitlement(jd, e["role"], e["annual_leave_special_extra"])


def test_simulation_entitlement_varies():
    # join date / 職位唔同 → 額度有差異; 2026 入職嘅唔會多過足年額
    from simulate import ROLE_ANNUAL_BASE
    employees, _ = generate()
    ents = {e["annual_leave_entitlement"] for e in employees}
    assert len(ents) > 1
    for e in employees:
        if e["join_date"].startswith("2026"):
            full = ROLE_ANNUAL_BASE[e["role"]] + e["annual_leave_special_extra"]
            assert e["annual_leave_entitlement"] <= full


# ---------- D) 社保供款 ----------

def test_social_security_deduction():
    # 月薪 30,000 clean 月: 應稅 30,000 → 年化 360,000 → 應課稅 216,000
    # 1,400+1,600+3,600+8,000+6,160 = 20,760 → 扣減後 14,532 → 月稅 1,211
    # 實發 = 30,000 - 1,211 - 30 (僱員社保, 稅後扣) = 28,759
    # 僱主供款 60 係公司成本, 唔扣員工
    s = compute_payslip(mkemp(30000), [work(day=d) for d in range(1, 5)])
    assert s["deductions"]["social_security"] == 30.0
    assert s["social_security_employee"] == 30.0
    assert s["social_security_employer"] == 60.0
    assert s["taxable_income"] == 30000.0  # 社保唔扣減應稅工資
    assert s["tax_withheld"] == 1211.0
    assert s["net_pay"] == 28759.0


def test_simulation_fss_totals():
    # 100 人 × 僱員 30 = 3,000; 僱主 60 = 6,000
    slips, totals = _run()
    assert totals["total_fss_employee"] == 3000.0
    assert totals["total_fss_employer"] == 6000.0
    assert all(s["deductions"]["social_security"] == 30.0 for s in slips)


# ---------- E) 法定假日工作 / 颱風 ----------

def test_holiday_work_triple():
    # 月薪 30,000 (日薪 1,000): 強制性假日工作 1 天 → 額外 2,000 (三工: 月薪已含當日)
    # 應稅 32,000 → 稅 1,365 → 實發 32,000 - 1,365 - 30 = 30,605
    recs = [dict(work(day=1), type="holiday_work")]
    s = compute_payslip(mkemp(30000), recs)
    assert s["holiday_work_days"] == 1
    assert s["holiday_work_extra"] == 2000.0
    assert s["taxable_income"] == 32000.0
    assert s["tax_withheld"] == 1365.0
    assert s["net_pay"] == 30605.0


def test_holiday_work_comp_leave_option():
    # 強制性假日工作選補假: 額外只計 1× 日薪, 另欠有薪補假 1 日
    # 應稅 31,000 → 稅 1,288 → 實發 31,000 - 1,288 - 30 = 29,682
    recs = [dict(work(day=1), type="holiday_work", comp_leave=True)]
    s = compute_payslip(mkemp(30000), recs)
    assert s["holiday_work_extra"] == 1000.0
    assert s["comp_leave_owed_days"] == 1
    assert s["taxable_income"] == 31000.0
    assert s["tax_withheld"] == 1288.0
    assert s["net_pay"] == 29682.0


def test_restday_work_double():
    # 週假工作 1 天 → 額外 1,000 (雙工); 應稅 31,000 → 稅 1,288 → 實發 29,682
    recs = [dict(work(day=1), type="restday_work")]
    s = compute_payslip(mkemp(30000), recs)
    assert s["restday_work_days"] == 1
    assert s["restday_work_extra"] == 1000.0
    assert s["taxable_income"] == 31000.0
    assert s["tax_withheld"] == 1288.0
    assert s["net_pay"] == 29682.0


def test_restday_work_comp_leave_option():
    # 週假工作選補休: 額外現金 0, 欠有薪補假 1 日; 應稅 30,000 → 稅 1,211
    recs = [dict(work(day=1), type="restday_work", comp_leave=True)]
    s = compute_payslip(mkemp(30000), recs)
    assert s["restday_work_extra"] == 0.0
    assert s["comp_leave_owed_days"] == 1
    assert s["net_pay"] == 28759.0


def test_comp_leave_is_paid():
    # 補假日: 有薪不扣; 之後唔再欠補假
    recs = [dict(work(day=1), type="holiday_work", comp_leave=True),
            {"date": "2026-09-02", "shift": "早", "type": "comp_leave",
             "cert": True, "late_min": 0.0, "ot_hours": 0.0}]
    s = compute_payslip(mkemp(30000), recs)
    assert s["comp_leave_days"] == 1
    assert s["comp_leave_owed_days"] == 0
    assert s["taxable_income"] == 31000.0
    assert s["net_pay"] == 29682.0


def test_typhoon_work_policy():
    # 颱風期間工作 1 天 (公司政策: 額外 1× 日薪 + 定額津貼 500/日)
    # 應稅 31,500 → 稅 1,326.5 → 實發 31,500 - 1,326.5 - 30 = 30,143.5
    import payslip
    old = payslip.TYPHOON_ALLOWANCE
    payslip.TYPHOON_ALLOWANCE = 500.0
    try:
        recs = [dict(work(day=1), type="typhoon_work")]
        s = compute_payslip(mkemp(30000), recs)
        assert s["typhoon_work_days"] == 1
        assert s["typhoon_work_extra"] == 1000.0
        assert s["typhoon_allowance"] == 500.0
        assert s["taxable_income"] == 31500.0
        assert s["tax_withheld"] == 1326.5
        assert s["net_pay"] == 30143.5
    finally:
        payslip.TYPHOON_ALLOWANCE = old


def test_simulation_holiday_and_restday_work():
    # 2026-09-26 (中秋節翌日) 有員工計三工; 週假工作有雙工記錄
    slips, totals = _run()
    assert totals["total_holiday_work_extra"] > 0
    assert any(s["holiday_work_days"] > 0 for s in slips)
    assert any(s["restday_work_days"] > 0 for s in slips)
    for s in slips:
        daily = s["monthly_salary"] / 30.0
        assert abs(s["holiday_work_extra"] - s["holiday_work_days"] * daily * 2.0) < 0.02
        assert abs(s["restday_work_extra"] - s["restday_work_days"] * daily * 1.0) < 0.02


def test_report_csv_rows():
    # report.py 輸出 100 行, 實發合計同 totals 一致
    from report import build_rows, FLAT_KEYS
    employees, records = generate()
    rows, totals = build_rows(employees, records)
    assert len(rows) == 100
    assert all(set(FLAT_KEYS) <= set(r) for r in rows)
    assert abs(sum(r["net_pay"] for r in rows) - totals["total_net"]) < 0.02


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
