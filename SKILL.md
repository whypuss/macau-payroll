# macau-payroll

澳門薪金計算 skill: 由出勤/輪更/請假計到實發工資, 再計職業稅。
**所有計算由確定性 Python 代碼執行, 絕不由 LLM 即場計數。**

## 模組

| 檔案 | 用途 |
|---|---|
| `payroll.py` | 職業稅計算 (年稅 / 月代扣 / 年實收) |
| `simulate.py` | 模擬 100 員工 × 2026年9月: 輪更、打卡、年假/病假/無薪假 |
| `payslip.py` | 糧單計算: 出勤記錄 → 應稅工資 → 稅 → 實發 |
| `test_payroll.py` | 13 tests: 稅制 (預期值人手按官方稅表計出) |
| `test_payslip.py` | 18 tests: 人手糧單個案 + 年假額度 + 100 人模擬不變量 |
| `data/` | 模擬數據 (employees.json, records.json, 供檢查) |

## 完整流程

```bash
cd ~/workspace/skills/macau-payroll
python3 simulate.py          # 生成 100 人模擬數據 → data/
python3 test_payroll.py      # 13 tests, 稅制
python3 test_payslip.py      # 18 tests, 糧單
```

```python
from simulate import generate
from payslip import payroll_run

employees, records = generate()      # 確定性隨機, seed 固定
slips, totals = payroll_run(employees, records)
# totals: headcount / total_taxable / total_tax / total_net ...

from payslip import compute_payslip
slip = compute_payslip(employees[0], records["E001"])
# slip: 月薪/日薪, 夜更津貼, 加班費, 各類假期日數,
#       deductions 明細, taxable_income, tax_withheld, net_pay
```

## 糧單計算規則

```
應稅工資 = 月薪 + 夜更津貼 + 加班費
           - 無薪假扣款 - 缺勤扣款 - 無證病假扣款 - 遲到扣款
稅款 = monthly_withholding(應稅工資)
實發 = 應稅工資 - 稅款
```

模擬假設 (非法律意見, 實際執行前請 HR 核實):
- 日薪 = 月薪 / 30, 時薪 = 日薪 / 8
- 年假額度: 經理 15 / 主任 13 / 職員 12 / 助理 10 天/年;
  特殊員工 +2~4 天; 入職當年按 (13−入職月份)/12 比例計
- 年假: 額度內全薪不扣, 超出部份當無薪假扣
- 病假: 有醫生證明全薪, 無證明扣日薪
- 無薪假 / 缺勤: 扣日薪; 遲到: 5 分鐘寬限後按分鐘扣
- 夜更津貼 MOP 80/更; 加班 1.5 倍時薪

## 稅制參數 (2025/2026 財政年度, 會隨每年預算案變)

- 年豁免額: MOP 144,000
- 級距 (按 應課稅收益 = 年收入 − 不課稅收益 − 豁免額):
  首 20,000 → 7%; 其後 20,000 → 8%; 其後 40,000 → 9%;
  其後 80,000 → 10%; 其後 120,000 → 11%; 餘額 → 12%
- 稅額扣減率: 30%

資料來源: 財政局《職業稅計算法》、第13/2025號法律第18條 (2026年度)、
第25/2024號法律第19條 (2025年度)。新財政年度預算案公佈後要核對參數。

## 驗證紀律 (重要)

- 計算正確性由兩個 test files 共 31 個 tests 保證, 唔係由 AI「睇過」保證。
- 人手個案的預期值全部人手計出, 非生成; 模擬不變量驗證會計恆等式
  (實發+稅+扣款 == 月薪+津貼+加班費)、非負、扣款公式、確定性。
- 改動任何計算代碼或參數後, 必須兩個 test files 全部 PASS 先算完成。
- 唔好叫任何 LLM (包括 Kev) 去「驗證」算術: 概率模型俾唔到 100% 保證,
  佢自己計數都會錯。Kev 只適合判斷類問題 (例如「呢筆收入應唔應該課稅」),
  唔適合驗證數字。
