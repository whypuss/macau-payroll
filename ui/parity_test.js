/* JS 版 vs Python 版對數: 逐張糧單逐個欄位比較 */
const fs = require("fs");
const path = require("path");
const core = require("./payroll-core.js");

const dir = path.join(__dirname, "..");
const employees = JSON.parse(fs.readFileSync(path.join(dir, "data/employees.json"), "utf8"));
const records = JSON.parse(fs.readFileSync(path.join(dir, "data/records.json"), "utf8"));
const expected = JSON.parse(fs.readFileSync(path.join(__dirname, "expected.json"), "utf8"));

const { slips } = core.payrollRun(employees, records);
const FIELDS = ["monthly_salary", "daily_rate", "night_allowance", "overtime_pay",
  "holiday_work_extra", "restday_work_extra", "typhoon_work_extra", "typhoon_allowance",
  "taxable_income", "tax_withheld", "net_pay", "deductions"];
let maxDiff = 0, diffFields = 0, exact = 0, total = 0;
for (const s of slips) {
  const e = expected.slips[s.id];
  for (const f of FIELDS) {
    total++;
    const a = (f === "deductions") ? s.deductions.total : s[f];
    const d = Math.abs(a - e[f]);
    maxDiff = Math.max(maxDiff, d);
    if (d === 0) exact++; else diffFields++;
  }
}
console.log(`slips=${slips.length} fields=${total} exact=${exact} diffs=${diffFields} maxDiff=${maxDiff}`);
const t = core.payrollRun(employees, records).totals;
let tdiff = 0;
for (const k of Object.keys(expected.totals)) {
  tdiff = Math.max(tdiff, Math.abs(t[k] - expected.totals[k]));
}
console.log("totals maxDiff=" + tdiff);
if (maxDiff > 0.011 || tdiff > 0.011) { console.error("PARITY FAIL"); process.exit(1); }
console.log("PARITY OK");
