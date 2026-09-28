"""macau-payroll 的 unit tests。

所有 expected 值均為人手按財政局官方《職業稅計算法》計出,
非由程式或 AI 生成。改動 payroll.py 後必須全部通過。

官方級距 (應課稅收益 = 年收入 - 144,000):
  首 20,000 → 7% | 其後 20,000 → 8% | 其後 40,000 → 9%
  其後 80,000 → 10% | 其後 120,000 → 11% | 餘額 → 12%
稅額扣減 30%。
"""
from payroll import annual_tax, monthly_withholding, annual_net


def test_exempt_below_threshold():
    r = annual_tax(144000)
    assert r["taxable_income"] == 0.0
    assert r["tax_payable"] == 0.0


def test_below_exemption():
    r = annual_tax(100000)
    assert r["tax_payable"] == 0.0


def test_bracket_7pct():
    # 應課稅 20,000 → 20,000×7% = 1,400 → 扣減30% = 980
    r = annual_tax(164000)
    assert r["taxable_income"] == 20000.0
    assert r["tax_before_reduction"] == 1400.0
    assert r["tax_payable"] == 980.0


def test_bracket_8pct():
    # 應課稅 40,000 → 1,400+1,600 = 3,000 → 2,100
    r = annual_tax(184000)
    assert r["tax_before_reduction"] == 3000.0
    assert r["tax_payable"] == 2100.0


def test_bracket_9pct():
    # 應課稅 80,000 → 3,000+3,600 = 6,600 → 4,620
    r = annual_tax(224000)
    assert r["tax_before_reduction"] == 6600.0
    assert r["tax_payable"] == 4620.0


def test_bracket_10pct():
    # 應課稅 160,000 → 6,600+8,000 = 14,600 → 10,220
    r = annual_tax(304000)
    assert r["tax_before_reduction"] == 14600.0
    assert r["tax_payable"] == 10220.0


def test_bracket_11pct():
    # 應課稅 280,000 → 14,600+13,200 = 27,800 → 19,460
    r = annual_tax(424000)
    assert r["tax_before_reduction"] == 27800.0
    assert r["tax_payable"] == 19460.0


def test_top_bracket_12pct():
    # 年收 500,000 → 應課稅 356,000
    # 27,800 + 76,000×12% = 27,800+9,120 = 36,920 → 25,844
    r = annual_tax(500000)
    assert r["taxable_income"] == 356000.0
    assert r["tax_before_reduction"] == 36920.0
    assert r["tax_payable"] == 25844.0


def test_non_taxable_deduction():
    # 年收 200,000, 不課稅 56,000 → 應課稅 0
    r = annual_tax(200000, non_taxable=56000)
    assert r["taxable_income"] == 0.0
    assert r["tax_payable"] == 0.0


def test_breakdown_sums_correctly():
    # 明細加總必須等於稅前總額 (內部一致性)
    r = annual_tax(500000)
    total = round(sum(b["tax"] for b in r["breakdown"]), 2)
    assert total == r["tax_before_reduction"]


def test_monthly_withholding():
    # 月薪 25,000 → 年化 300,000 → 應課稅 156,000
    # 1,400+1,600+3,600+7,600 = 14,200 → 9,940/年 → 828.33/月
    r = monthly_withholding(25000)
    assert r["annual_tax_payable"] == 9940.0
    assert r["monthly_tax_withheld"] == 828.33
    assert r["monthly_net"] == 24171.67


def test_annual_net():
    r = annual_net(300000)
    assert r["tax_payable"] == 9940.0
    assert r["annual_net"] == 290060.0


def test_negative_income_rejected():
    try:
        annual_tax(-1000)
    except ValueError:
        return
    raise AssertionError("negative income should raise ValueError")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
