#!/usr/bin/env python3
"""HR 報表: 計 100 人糧單, 輸出 payslips_2026-09.csv (Excel 直接開到)。

用法 (唔使安裝任何嘢, 純 Python 標準庫):
    python report.py
"""
import csv
import os

from payslip import payroll_run
from simulate import generate

COLUMNS = [
    ("id", "員工編號"), ("name", "姓名"), ("role", "職位"),
    ("monthly_salary", "月薪"), ("daily_rate", "日薪"),
    ("night_allowance", "夜更津貼"), ("overtime_pay", "加班費"),
    ("holiday_work_extra", "強制性假日工作額外報酬"),
    ("restday_work_extra", "週假工作額外報酬"),
    ("typhoon_work_extra", "颱風工作額外報酬"),
    ("typhoon_allowance", "颱風津貼"),
    ("taxable_income", "應稅工資"), ("tax_withheld", "職業稅"),
    ("fss_employee", "社保僱員供款"), ("net_pay", "實發工資"),
    ("comp_leave_owed_days", "欠補假日數"),
]

FLAT_KEYS = [k for k, _ in COLUMNS]


def build_rows(employees, records):
    slips, totals = payroll_run(employees, records)
    rows = []
    for s in slips:
        row = {k: s[k] for k in FLAT_KEYS if k != "fss_employee"}
        row["fss_employee"] = s["social_security_employee"]
        rows.append(row)
    return rows, totals


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    employees, records = generate()
    rows, totals = build_rows(employees, records)
    out = os.path.join(here, "payslips_2026-09.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[label for _, label in COLUMNS])
        w.writeheader()
        for r in rows:
            w.writerow({label: r[key] for key, label in COLUMNS})
    print(f"已輸出 {out} ({len(rows)} 人)")
    print(f"應稅總額 MOP {totals['total_taxable']:,.2f}")
    print(f"職業稅總額 MOP {totals['total_tax']:,.2f}")
    print(f"實發總額   MOP {totals['total_net']:,.2f}")
    print(f"僱員社保總額 MOP {totals['total_fss_employee']:,.2f} / "
          f"僱主社保總額 MOP {totals['total_fss_employer']:,.2f}")


if __name__ == "__main__":
    main()
