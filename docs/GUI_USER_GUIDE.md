# GUI User Guide (繁體中文 / English)

## 啟動 / Starting the app

**Windows 一鍵啟動 / Windows one-click:**
No exe is shipped pre-built — build it once with
`pip install ".[packaging]"` then `powershell -File release/windows/build.ps1`
(see README's "Windows One-Click Application" section). That produces
`dist\windows\UniversalTest\UniversalTest.exe`. From then on, just
double-click that file (or copy the whole `UniversalTest` folder anywhere,
including a machine with no Python installed). The app runs windowed (no
console window) and your default browser opens automatically to
`http://127.0.0.1:<port>`. If the browser doesn't open automatically, a
small dialog box pops up showing the address to open manually.

**From a terminal (if you already have the CLI installed):**

```bash
universal-test gui
```

Optional flags: `--port <N>` (pick a specific local port), `--no-browser`
(don't auto-open a browser).

The tool never listens on anything other than `127.0.0.1` — it cannot be
reached from another computer on your network.

## 第一次使用 / First run

On first launch you'll see a short welcome screen explaining what the
tool checks (project structure, API functionality, performance, database,
regressions) — no programming knowledge required.

## 基本流程 / Basic flow

1. **選擇專案資料夾 / Choose Project Folder** — click "選擇資料夾" and pick
   the folder of the project you want to check.
2. **測試目標（選填）/ Test Target (optional)** — if you have a running
   instance of the service (e.g. `http://localhost:8000`), enter its
   address. If you leave this empty, Universal Test will not send any
   traffic anywhere — it only analyzes the project's source.
3. **檢查項目 / Checks to run** — by default, "專案分析與功能測試" is on;
   "效能測試" and "資料庫檢查" are off. Turn them on only if you want them.
   - Performance testing requires a second confirmation checkbox because
     it sends real traffic to your test target.
   - Database checking requires a database profile file (Advanced
     Settings) and always connects read-only.
4. Click **開始專案健檢 / Start Assessment**.
5. Watch the progress screen — each step is described in plain language,
   not technical jargon. A "比較 Baseline（回歸檢查）" (Regression) step
   only appears in the checklist when you provided a baseline file; it's
   left out entirely otherwise, since it never actually runs.
6. Review the **result dashboard**:
   - Overall status: 🟢 通過 (Pass) / 🟡 需要注意 (Needs Attention) /
     🔴 發現問題 (Issues Found) / ⚪ 無法評估 (Unknown). There is no
     numeric score by design.
   - **品質關卡 / Quality Gate** — the same PASS/WARNING/FAIL/ERROR
     verdict and exit code your CI pipeline would get from
     `universal-test assess`, shown with its reason and any findings.
   - **回歸比較 / Regression** — shown only when you provided a baseline
     file; 🟢 no regression detected, or a list of what changed
     (functional tests that flipped PASS→FAIL, performance metrics that
     crossed a threshold, etc.). This is the exact same comparison
     `universal-test baseline compare` computes — the GUI only renders it.
   - Category cards (專案分析 Project Discovery, 建置與專案健康度
     Build/Project Health, 可測試性 Testability, 功能健康度 Functional
     Health, 效能 Performance, 設定檔健全度 Configuration Hygiene, 測試
     基礎設施 Test Infrastructure, 資料庫健康度 Database Health) — click
     one to jump to its findings.
   - "尚未檢查" (Not Checked) lists anything that was skipped and *why* —
     this is never the same thing as "passed."
   - "發現的問題" (Findings) lists concrete problems in plain language,
     each with a "查看技術細節" (View technical details) toggle for
     endpoint/status/evidence data.
7. Use the report buttons to open the full HTML report, export
   JSON/Markdown, or open the folder the reports were saved to.

If something goes wrong unexpectedly, the GUI shows a plain-language error
message and an **error ID** — never a raw Python traceback, password,
token, or connection string. The full technical detail (redacted of any
secret) is written to the application's own log, not to the browser.

## 效能測試 API 選擇 / Performance endpoint selection

When you enable "效能測試" (Performance Testing), the GUI looks at your
project's OpenAPI spec:

- **One safe candidate** — it's selected automatically.
- **Several candidates** — you'll see a list of `METHOD /path` options to
  choose from (this list comes straight from the same OpenAPI parsing the
  CLI uses; the browser never parses the spec itself).
- **No OpenAPI spec found** — the GUI explains why performance testing
  can't run and what to do (point it at a spec file, or use the CLI's
  `--endpoint`/`--method` flags directly).

## API 驗證設定 / API Authentication

Under "進階設定" (Advanced Settings) you can configure authentication for
the API being tested: none, Bearer token, API key, or Basic auth. Every
field is the **name of an environment variable** (e.g. `API_TOKEN`), never
the secret value itself — the GUI reads that variable's value only at test
execution time, the same way the CLI's `--bearer-token-env` flag does. The
actual credential is never stored, displayed, or written into any report
or log.

## 進階設定 / Advanced Settings

Hidden behind "進階設定" by default:

- An explicit OpenAPI spec file (if your project has more than one).
- Performance test profile/timeout.
- A baseline file to compare the current run against (regression check).
- The report output folder.
- API authentication (see above).

## 語言 / Language

Toggle between 繁體中文 and English at the top of the window at any time.

## CLI still available

The GUI is an additional interface, not a replacement. Every existing
command still works exactly as before:

```bash
universal-test scan ./project
universal-test test ./project --target http://localhost:8000
universal-test performance ./project --target http://localhost:8000 --yes
universal-test database ./project --database-profile profile.yaml
universal-test assess ./project
universal-test baseline save ./project --output baseline.json
```
