#!/usr/bin/env python3
"""模擬 100 名員工 2026年9月 的輪更 / 打卡 / 請假數據。

確定性隨機 (seed 固定), 每次生成結果完全相同。
輸出: data/employees.json, data/records.json (供人檢查用);
      test 直接 call generate() 唔依賴檔案。

模擬假設 (非法律意見, 實際執行前請 HR 核實):
- 日薪 = 月薪 / 30, 時薪 = 日薪 / 8
- 年假額度: 經理 15 / 主任 13 / 職員 12 / 助理 10 天/年;
  特殊員工 +2~4 天; 入職當年按 (13-入職月份)/12 比例計
- 年假: 額度內全薪不扣, 超出部份當無薪假扣
- 病假: 有醫生證明全薪; 無證明扣日薪
- 無薪假 / 缺勤: 扣日薪
- 遲到: 5 分鐘寬限, 之後按分鐘扣 (時薪/60)
- 夜更津貼: MOP 80 / 更
- 加班: 收工超時按 1.5 倍時薪計
"""
import json
import os
import random
from datetime import date

SEED = 20260928
YEAR, MONTH, DAYS_IN_MONTH = 2026, 9, 30

SURNAMES = ["陳", "林", "黃", "張", "李", "吳", "劉", "蔡", "楊", "許",
            "鄭", "謝", "郭", "王", "曾", "鍾", "蕭", "羅", "梁", "何"]
GIVEN_A = ["偉", "芳", "俊", "敏", "健", "靜", "志", "麗", "子", "家",
           "文", "曉", "永", "淑", "建", "佩", "國", "美", "嘉", "思"]
GIVEN_B = ["明", "華", "強", "英", "玲", "軍", "傑", "婷", "豪", "怡",
           "峰", "欣", "儀", "賢", "雯", "龍", "鳳", "珊", "浩", "君"]

# (職位, 最低月薪, 最高月薪, 人數)
ROLES = [
    ("經理", 38000, 55000, 8),
    ("主任", 26000, 36000, 15),
    ("職員", 15000, 24000, 45),
    ("助理", 12000, 16000, 32),
]

# 年假額度 (公司政策, 天/年)
ROLE_ANNUAL_BASE = {"經理": 15, "主任": 13, "職員": 12, "助理": 10}


def annual_entitlement(join_date, role, special_extra=0):
    """年假額度: 職位基本額 + 特殊加額; 入職當年按比例 (包含入職當月)。"""
    base = ROLE_ANNUAL_BASE[role] + special_extra
    if join_date.year < YEAR:
        return base
    months = 13 - join_date.month
    return max(1, round(base * months / 12))

SHIFT_NAMES = ["早", "晚", "夜"]
# 上班/收工時間 (分鐘, 由 00:00 起計)
SHIFT_TIME = {"早": (480, 960), "晚": (960, 1440), "夜": (0, 480)}


def generate(seed=SEED):
    rng = random.Random(seed)
    employees = []
    records = {}  # emp_id -> [record]

    idx = 0
    for role, lo, hi, headcount in ROLES:
        for _ in range(headcount):
            idx += 1
            emp_id = f"E{idx:03d}"
            name = rng.choice(SURNAMES) + rng.choice(GIVEN_A) + rng.choice(GIVEN_B)
            salary = round(rng.uniform(lo, hi) / 100) * 100
            shift_mode = "rotating" if rng.random() < 0.6 else rng.choice(SHIFT_NAMES)
            rest_weekday = idx % 7  # 每週休一日, 輪流
            # 入職日期: 七成 2019-2025 入職, 三成 2026 年內入職 (按比例計年假)
            if rng.random() < 0.7:
                join_date = date(rng.randint(2019, 2025), rng.randint(1, 12), 1)
            else:
                join_date = date(YEAR, rng.randint(1, 8), 1)
            special_extra = rng.randint(2, 4) if rng.random() < 0.1 else 0  # 特殊員工加額
            entitlement = annual_entitlement(join_date, role, special_extra)
            employees.append({
                "id": emp_id, "name": name, "role": role,
                "monthly_salary": salary, "shift_mode": shift_mode,
                "rest_weekday": rest_weekday,
                "join_date": join_date.isoformat(),
                "annual_leave_entitlement": entitlement,
                "annual_leave_special_extra": special_extra,
            })

    for emp in employees:
        recs = []
        # 該月工作日 (非休息日)
        workdays = [d for d in range(1, DAYS_IN_MONTH + 1)
                    if date(YEAR, MONTH, d).weekday() != emp["rest_weekday"]]

        def shift_of(day):
            if emp["shift_mode"] == "rotating":
                return SHIFT_NAMES[(day + int(emp["id"][1:])) % 3]
            return emp["shift_mode"]

        # 預先決定請假日數, 隨機抽日 (年假唔可以超過額度)
        n_annual = min(rng.choices([0, 1, 2, 3], weights=[55, 25, 12, 8])[0],
                       emp["annual_leave_entitlement"])
        n_sick = rng.choices([0, 1, 2], weights=[70, 22, 8])[0]
        n_nopay = rng.choices([0, 1, 2], weights=[75, 18, 7])[0]
        n_absent = rng.choices([0, 1], weights=[93, 7])[0]
        leave_days = rng.sample(workdays, min(len(workdays),
                               n_annual + n_sick + n_nopay + n_absent))
        leave_map = {}
        pos = 0
        for _ in range(n_annual):
            leave_map[leave_days[pos]] = ("annual", True); pos += 1
        for _ in range(n_sick):
            leave_map[leave_days[pos]] = ("sick", rng.random() < 0.7); pos += 1
        for _ in range(n_nopay):
            leave_map[leave_days[pos]] = ("nopay", True); pos += 1
        for _ in range(n_absent):
            leave_map[leave_days[pos]] = ("absent", True); pos += 1

        for d in workdays:
            shift = shift_of(d)
            start, end = SHIFT_TIME[shift]
            if d in leave_map:
                ltype, cert = leave_map[d]
                recs.append({"date": f"{YEAR}-{MONTH:02d}-{d:02d}",
                             "shift": shift, "type": ltype, "cert": cert,
                             "late_min": 0.0, "ot_hours": 0.0})
                continue
            # 打卡: 返工時間偏移
            r = rng.random()
            if r < 0.88:
                offset_in = rng.uniform(-5, 5)
            elif r < 0.95:
                offset_in = rng.uniform(5, 30)
            elif r < 0.98:
                offset_in = rng.uniform(30, 60)
            else:
                offset_in = rng.uniform(60, 120)
            # 收工: 兩成有加班
            if rng.random() < 0.20:
                offset_out = rng.uniform(30, 180)
            else:
                offset_out = rng.uniform(-10, 10)
            late_min = round(max(0.0, offset_in), 1)
            ot_hours = round(max(0.0, offset_out) / 60, 2)
            recs.append({"date": f"{YEAR}-{MONTH:02d}-{d:02d}",
                         "shift": shift, "type": "work", "cert": True,
                         "late_min": late_min, "ot_hours": ot_hours})
        records[emp["id"]] = recs

    return employees, records


def main():
    employees, records = generate()
    datadir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(datadir, exist_ok=True)
    with open(os.path.join(datadir, "employees.json"), "w") as f:
        json.dump(employees, f, ensure_ascii=False, indent=1)
    with open(os.path.join(datadir, "records.json"), "w") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    n_rec = sum(len(v) for v in records.values())
    print(f"{len(employees)} employees, {n_rec} records -> {datadir}/")


if __name__ == "__main__":
    main()
