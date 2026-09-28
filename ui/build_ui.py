#!/usr/bin/env python3
"""將 payroll-core.js + 模擬數據打包成單檔 payroll-ui.html (零依賴, 雙擊即用)。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    with open(os.path.join(HERE, "payroll-core.js"), encoding="utf-8") as f:
        core = f.read()
    with open(os.path.join(ROOT, "data", "employees.json"), encoding="utf-8") as f:
        emp = f.read()
    with open(os.path.join(ROOT, "data", "records.json"), encoding="utf-8") as f:
        rec = f.read()

    def safe(s):
        return s.replace("</script", "<\\/script")

    html = (tpl.replace("/*__CORE_JS__*/", safe(core))
               .replace("/*__EMPLOYEES__*/", safe(emp))
               .replace("/*__RECORDS__*/", safe(rec)))
    out = os.path.join(ROOT, "payroll-ui.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已產生 {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
