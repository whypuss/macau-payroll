/* macau-payroll 核心計算 (JS 版, 與 Python 版公式一致)。
 * 稅制: 2025/2026 財政年度, 年豁免額 MOP 144,000, 稅額扣減 30%。
 * 注意: pyRound 模仿 Python round() (banker's rounding)。
 */
"use strict";

// --- 稅制參數 ---
const BRACKETS = [
  [20000, 0.07],
  [40000, 0.08],
  [80000, 0.09],
  [160000, 0.10],
  [280000, 0.11],
  [Infinity, 0.12],
];
const EXEMPTION = 144000.0;
const REDUCTION_RATE = 0.30;

// --- 糧單參數 ---
const NIGHT_ALLOWANCE = 80.0;   // MOP / 更
const LATE_GRACE_MIN = 5.0;     // 遲到寬限分鐘
const OVERTIME_MULT = 1.5;      // 加班倍率
const FSS_EMPLOYEE = 30.0;      // 社保僱員供款 MOP/月 (稅後代扣)
const FSS_EMPLOYER = 60.0;      // 社保僱主供款 MOP/月 (公司成本)
const HOLIDAY_EXTRA_MULT = 2.0; // 強制性假日工作: 額外 2x 日薪 (三工)
const RESTDAY_EXTRA_MULT = 1.0; // 週假工作: 額外 1x 日薪 (雙工)
// 颱風屬公司政策, UI 可調
let TYPHOON_EXTRA_MULT = 1.0;
let TYPHOON_ALLOWANCE = 0.0;

const WORK_TYPES = ["work", "holiday_work", "restday_work", "typhoon_work"];

// 模仿 Python round(): 對 double 的精確十進制值做 round-half-even。
// 用 BigInt 做精確有理數運算, 再轉回最接近的 double。
function pyRound(x, nd) {
  nd = nd || 0;
  if (x === 0 || !isFinite(x) || isNaN(x)) return x;
  const neg = x < 0;
  const dv = new DataView(new ArrayBuffer(8));
  dv.setFloat64(0, Math.abs(x));
  const hi = dv.getUint32(0), lo = dv.getUint32(4);
  const expBits = (hi >>> 20) & 0x7ff;
  let mant = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
  let e2;
  if (expBits === 0) { e2 = -1074; }
  else { mant |= (1n << 52n); e2 = expBits - 1075; }
  // value = mant * 2^e2; 求 round_half_even(value * 10^nd)
  const scale = 10n ** BigInt(nd);
  let num, den;
  if (e2 >= 0) { num = mant * scale * (2n ** BigInt(e2)); den = 1n; }
  else { num = mant * scale; den = 2n ** BigInt(-e2); }
  let q = num / den;
  const r = num % den;
  const twice = r * 2n;
  if (twice > den || (twice === den && (q & 1n) === 1n)) q += 1n;
  let s = q.toString(), dec;
  if (nd === 0) dec = s;
  else {
    while (s.length <= nd) s = "0" + s;
    dec = s.slice(0, s.length - nd) + "." + s.slice(s.length - nd);
  }
  const res = Number(dec);
  return neg ? -res : res;
}

function annualTax(annualIncome, nonTaxable) {
  nonTaxable = nonTaxable || 0;
  if (annualIncome < 0 || nonTaxable < 0) throw new Error("income must be >= 0");
  const taxable = Math.max(0, annualIncome - nonTaxable - EXEMPTION);
  let prevCap = 0, beforeReduction = 0;
  for (const [cap, rate] of BRACKETS) {
    if (taxable <= prevCap) break;
    const amt = Math.min(taxable, cap) - prevCap;
    beforeReduction += amt * rate;
    prevCap = cap;
  }
  return pyRound(beforeReduction * (1 - REDUCTION_RATE), 2);
}

function monthlyWithholding(monthlySalary) {
  return pyRound(annualTax(monthlySalary * 12) / 12, 2);
}

function computePayslip(emp, records) {
  const monthly = Number(emp.monthly_salary);
  const daily = monthly / 30.0;
  const hourly = daily / 8.0;
  const isWork = (r) => WORK_TYPES.indexOf(r.type) >= 0;

  const nightShifts = records.filter((r) => isWork(r) && r.shift === "夜").length;
  const allowance = pyRound(nightShifts * NIGHT_ALLOWANCE, 2);

  const otHours = pyRound(
    records.filter(isWork).reduce((a, r) => a + Number(r.ot_hours || 0), 0), 2);
  const otPay = pyRound(otHours * hourly * OVERTIME_MULT, 2);

  const holidayRecs = records.filter((r) => r.type === "holiday_work");
  const restdayRecs = records.filter((r) => r.type === "restday_work");
  const typhoonRecs = records.filter((r) => r.type === "typhoon_work");
  const holidayExtra = pyRound(holidayRecs.reduce(
    (a, r) => a + daily * (HOLIDAY_EXTRA_MULT - (r.comp_leave ? 1.0 : 0.0)), 0), 2);
  const restdayExtra = pyRound(restdayRecs.reduce(
    (a, r) => a + daily * (RESTDAY_EXTRA_MULT - (r.comp_leave ? 1.0 : 0.0)), 0), 2);
  const typhoonExtra = pyRound(typhoonRecs.length * daily * TYPHOON_EXTRA_MULT, 2);
  const typhoonAllow = pyRound(typhoonRecs.length * TYPHOON_ALLOWANCE, 2);
  const compLeaveDays = records.filter((r) => r.type === "comp_leave").length;
  const compLeaveOwed = Math.max(0,
    holidayRecs.concat(restdayRecs).filter((r) => r.comp_leave).length - compLeaveDays);

  const nopayDays = records.filter((r) => r.type === "nopay").length;
  const absentDays = records.filter((r) => r.type === "absent").length;
  const sickUncertDays = records.filter((r) => r.type === "sick" && !r.cert).length;
  const annualDays = records.filter((r) => r.type === "annual").length;

  const entitlement = parseInt(emp.annual_leave_entitlement || "12", 10);
  const excessAnnual = Math.max(0, annualDays - entitlement);

  const nopayDed = pyRound((nopayDays + excessAnnual) * daily, 2);
  const absentDed = pyRound(absentDays * daily, 2);
  const sickDed = pyRound(sickUncertDays * daily, 2);
  const lateMinTotal = pyRound(
    records.filter(isWork).reduce((a, r) => a + Math.max(0, Number(r.late_min || 0) - LATE_GRACE_MIN), 0), 1);
  const lateDed = pyRound(lateMinTotal * hourly / 60.0, 2);

  const deductions = pyRound(nopayDed + absentDed + sickDed + lateDed, 2);
  const extras = pyRound(allowance + otPay + holidayExtra + restdayExtra + typhoonExtra + typhoonAllow, 2);
  const taxable = pyRound(Math.max(0, monthly + extras - deductions), 2);
  const tax = monthlyWithholding(taxable);
  const net = pyRound(Math.max(0, taxable - tax - FSS_EMPLOYEE), 2);

  return {
    id: emp.id, name: emp.name, role: emp.role,
    monthly_salary: pyRound(monthly, 2),
    daily_rate: pyRound(daily, 2),
    night_shifts: nightShifts, night_allowance: allowance,
    ot_hours: otHours, overtime_pay: otPay,
    holiday_work_days: holidayRecs.length, holiday_work_extra: holidayExtra,
    restday_work_days: restdayRecs.length, restday_work_extra: restdayExtra,
    typhoon_work_days: typhoonRecs.length, typhoon_work_extra: typhoonExtra,
    typhoon_allowance: typhoonAllow,
    comp_leave_days: compLeaveDays, comp_leave_owed_days: compLeaveOwed,
    annual_leave_days: annualDays,
    annual_leave_entitlement: entitlement,
    annual_leave_excess_days: excessAnnual,
    annual_leave_remaining: Math.max(0, entitlement - annualDays),
    nopay_days: nopayDays, absent_days: absentDays,
    sick_uncert_days: sickUncertDays,
    late_min_charged: lateMinTotal,
    deductions: {
      nopay: nopayDed, absent: absentDed, sick_uncertified: sickDed,
      late: lateDed, social_security: FSS_EMPLOYEE,
      total: pyRound(deductions + FSS_EMPLOYEE, 2),
    },
    social_security_employee: FSS_EMPLOYEE,
    social_security_employer: FSS_EMPLOYER,
    taxable_income: taxable, tax_withheld: tax, net_pay: net,
  };
}

function payrollRun(employees, records) {
  const slips = employees.map((e) => computePayslip(e, records[e.id] || []));
  const sum = (f) => pyRound(slips.reduce((a, s) => a + f(s), 0), 2);
  return { slips, totals: {
    headcount: slips.length,
    total_taxable: sum((s) => s.taxable_income),
    total_tax: sum((s) => s.tax_withheld),
    total_net: sum((s) => s.net_pay),
    total_night_allowance: sum((s) => s.night_allowance),
    total_overtime_pay: sum((s) => s.overtime_pay),
    total_holiday_work_extra: sum((s) => s.holiday_work_extra),
    total_restday_work_extra: sum((s) => s.restday_work_extra),
    total_typhoon_work_extra: sum((s) => s.typhoon_work_extra),
    total_typhoon_allowance: sum((s) => s.typhoon_allowance),
    total_deductions: sum((s) => s.deductions.total),
    total_fss_employee: sum((s) => s.social_security_employee),
    total_fss_employer: sum((s) => s.social_security_employer),
  }};
}

if (typeof module !== "undefined") {
  module.exports = { pyRound, annualTax, monthlyWithholding, computePayslip, payrollRun };
}
