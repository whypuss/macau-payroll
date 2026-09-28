"""澳門職業稅 (payroll) 確定性計算模組。

稅制依據 (2025/2026 財政年度):
- 豁免額: MOP 144,000/年 (第13/2025號法律第18條; 2025年為第25/2024號法律第19條, 同額)
- 累進稅率 (財政局官方《職業稅計算法》, 按應課稅收益 = 年收入 - 豁免額):
    首 20,000             7%
    其後 20,000           8%    (20,001 - 40,000)
    其後 40,000           9%    (40,001 - 80,000)
    其後 80,000          10%    (80,001 - 160,000)
    其後 120,000         11%    (160,001 - 280,000)
    餘額                 12%
- 稅額扣減率: 30% (每年預算案訂定, 2025/2026 皆為 30%)

注意: 本模組只做數學計算, 不做判斷。所有數字必須經 test_payroll.py 驗證。
"""

# (級距上限, 稅率) — 上限為該級應課稅收益累計值
BRACKETS = [
    (20000, 0.07),
    (40000, 0.08),
    (80000, 0.09),
    (160000, 0.10),
    (280000, 0.11),
    (float("inf"), 0.12),
]

EXEMPTION = 144000.0   # 年豁免額 MOP
REDUCTION_RATE = 0.30  # 稅額扣減率


def annual_tax(annual_income, non_taxable=0.0,
               exemption=EXEMPTION, reduction=REDUCTION_RATE):
    """計全年職業稅。回傳 dict: breakdown 明細。

    annual_income: 全年金錢收益 (MOP)
    non_taxable:   不屬課稅收益 (MOP), 預設 0
    """
    if annual_income < 0 or non_taxable < 0:
        raise ValueError("income must be >= 0")
    taxable = max(0.0, annual_income - non_taxable - exemption)

    detail = []
    prev_cap = 0.0
    tax_before_reduction = 0.0
    for cap, rate in BRACKETS:
        if taxable <= prev_cap:
            break
        amount_in_bracket = min(taxable, cap) - prev_cap
        bracket_tax = amount_in_bracket * rate
        tax_before_reduction += bracket_tax
        detail.append({
            "bracket": f"{prev_cap:,.0f}-{cap:,.0f}" if cap != float("inf") else f">{prev_cap:,.0f}",
            "rate": rate,
            "taxable_in_bracket": round(amount_in_bracket, 2),
            "tax": round(bracket_tax, 2),
        })
        prev_cap = cap

    tax = round(tax_before_reduction * (1 - reduction), 2)
    return {
        "annual_income": round(annual_income, 2),
        "non_taxable": round(non_taxable, 2),
        "exemption": round(exemption, 2),
        "taxable_income": round(taxable, 2),
        "tax_before_reduction": round(tax_before_reduction, 2),
        "reduction_rate": reduction,
        "tax_payable": tax,
        "breakdown": detail,
    }


def monthly_withholding(monthly_salary, non_taxable_monthly=0.0, **kw):
    """估算每月代扣稅款: 年化後計全年稅再除以 12。"""
    annual = annual_tax(monthly_salary * 12, non_taxable_monthly * 12, **kw)
    monthly_tax = round(annual["tax_payable"] / 12, 2)
    return {
        "monthly_salary": round(monthly_salary, 2),
        "monthly_tax_withheld": monthly_tax,
        "monthly_net": round(monthly_salary - monthly_tax, 2),
        "annual_tax_payable": annual["tax_payable"],
    }


def annual_net(annual_income, **kw):
    """全年實收 = 年收入 - 應繳稅。"""
    r = annual_tax(annual_income, **kw)
    return {
        "annual_income": r["annual_income"],
        "tax_payable": r["tax_payable"],
        "annual_net": round(annual_income - r["tax_payable"], 2),
    }
