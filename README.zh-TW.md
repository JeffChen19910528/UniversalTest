# Universal Test

[English](README.md) | 繁體中文

一個與專案技術無關（project-agnostic）的 CLI 工具，用於對軟體專案進行初步品質評估：唯讀（read-only）探索、保守的 REST/OpenAPI 功能性測試、有界限的效能測試、唯讀的資料庫評估、基準線／回歸比較，以及一個確定性（deterministic）的 CI 品質關卡（Quality Gate）——並產出以證據為基礎的 JSON/Markdown/HTML 報告。

> **Universal Test 不是安全掃描工具、不是 QA 的替代品、不是正確性的保證，也不是自主（autonomous）測試代理人。** 它產出的是一份初步的、以證據為基礎的評估——保守、預設唯讀／安全（safe-by-default），且結果具確定性。詳見下方「限制」一節。

## 這個工具做什麼

給定一個陌生或你自己的專案，Universal Test 會：

1. **探索（Discover）**這個專案是什麼——語言、框架、建置系統、基礎設施、資料庫與 API 證據——過程中不會修改專案，也不會執行專案裡的任何程式碼。
2. **產生並執行保守的功能性測試**，針對 OpenAPI 規格——前提是你明確指定一個正在執行中的 API 實例作為目標。
3. **執行有界限並行數（bounded-concurrency）的效能測試**——但這是選擇性加入（opt-in）的功能。
4. **唯讀地評估資料庫結構（schema）**——前提是你明確提供憑證；絕不會執行任意 SQL。
5. **將本次執行結果與已儲存的基準線（baseline）比較**，以偵測回歸（regression）——涵蓋功能性、效能、資料庫結構與探索結果的變化。
6. **評估一個確定性的品質關卡（Quality Gate）**，並回傳一個穩定的 exit code，讓你的 CI pipeline 可以直接依此判斷。
7. **產出報告**：`report.json`／`report.md`／`report.html`——每一項發現（finding）都可追溯到具體證據，且 `UNKNOWN`／`NOT_ASSESSED`（未評估）是一級（first-class）的結果狀態，絕不會被悄悄地歸類為通過或失敗。

## 安裝

需要 Python 3.11 以上版本。

```bash
pip install universal-test
```

若要評估 SQL Server、PostgreSQL 或 MySQL 資料庫，需另外安裝選用的資料庫驅動程式擴充套件（SQLite 不需要，因為它使用 Python 標準函式庫）：

```bash
pip install "universal-test[database]"
```

## 快速開始

```bash
universal-test scan ./my-project
```

這個指令永遠是安全的：它是唯讀掃描，不會連上網路，也不會執行你專案中的任何程式碼。

如果你的專案有一個正在執行中的 API，可以用 `assess` 指向它：

```bash
universal-test assess ./my-project --target http://localhost:8000
```

在執行之前，有幾件事你應該先了解：

- **`--target` 必須明確指定。** Universal Test 絕不會自行猜測要測試的主機（host），OpenAPI 文件裡自帶的 `servers:` 欄位也絕不會被拿來當作替代目標。
- **`assess` 在沒有 `--target` 的情況下，不會產生任何網路流量**——它仍然會完成探索，並針對 Functional Health（功能健康度）與 Performance（效能）回報 `NOT_ASSESSED`（附上理由），而不是悄悄跳過。
- **效能測試是選擇性加入的功能**（`--performance`），且必須搭配 `--target` 使用；執行前一定會顯示測試計畫並要求確認才會送出真實流量（非互動模式下則需要 `--yes`）。
- **資料庫評估需要明確提供 `--database-profile`。** 在你的專案中偵測到「使用 PostgreSQL 相依套件」這件事，並不代表工具就有權限連線到該資料庫。
- **憑證絕不會從你的專案原始碼中自動讀取。** 憑證只會來自你在指令列中指定的具名環境變數（例如 `--bearer-token-env`，或是資料庫設定檔中的 `username_env`／`password_env` 等）。

## 圖形化介面（GUI）

不想打指令？`universal-test` 也內建一個在本機執行、以瀏覽器呈現的圖形化介面——不需要任何 Python、終端機或指令列知識。

```bash
universal-test gui
```

這個指令會在 `127.0.0.1`（僅限本機，網路上其他電腦絕對無法連線）啟動一個伺服器，並自動開啟你的預設瀏覽器。接下來你可以：

1. **選擇專案資料夾**——點選「選擇資料夾」，挑選你想檢查的專案。
2. **（網頁專案）使用「網頁應用程式健檢」卡片**——點選「分析專案並產生健檢計畫」，即可看到偵測結果與即將執行／不包含的項目，確認後一鍵執行；不需要理解下方「完整健檢」表單中的各種勾選項目。
3. **測試目標（選填）**——如果你有一個正在執行中的服務（例如 `http://localhost:8000`），在此輸入其位址。留空的話，Universal Test 不會對外發送任何流量，只會分析專案原始碼。
4. **選擇檢查項目（完整健檢）**——預設會開啟「專案分析與功能測試」；「效能測試」與「資料庫檢查」預設關閉，只有你主動勾選才會執行。效能測試需要額外勾選一個確認方塊（因為會對測試目標送出真實流量）；資料庫檢查需要在「進階設定」中提供資料庫設定檔，且一律唯讀連線。
5. 點選「**開始專案健檢**」。
5. 觀看進度畫面——每個步驟都以白話文說明。只有在你提供了 baseline 檔案時，畫面才會出現「比較 Baseline（回歸檢查）」這個步驟；沒有提供的話，這個步驟不會出現，因為它本來就不會執行。
6. 檢視**健檢結果**：
   - 整體狀態：🟢 通過／🟡 需要注意／🔴 發現問題／⚪ 無法評估——刻意不提供數字分數。
   - **品質關卡（Quality Gate）**——與 `universal-test assess` 在 CI 中回傳的 PASS／WARNING／FAIL／ERROR 判斷結果完全相同，並附上原因與相關發現。
   - **回歸比較**——只有在你提供了 baseline 檔案時才會顯示；🟢 未偵測到回歸問題，或列出實際的變化（例如某項功能測試從 PASS 變成 FAIL、某項效能指標超過門檻）。這與 `universal-test baseline compare` 計算出來的結果完全相同，GUI 只是把它畫出來，不會自己重新計算。
   - 分類卡片（專案分析、建置與專案健康度、可測試性、功能健康度、效能、設定檔健全度、測試基礎設施、資料庫健康度）——點選任一張卡片可跳到對應的發現項目。
   - 「尚未檢查」列出被跳過的項目與*原因*——這絕不等同於「通過」。
   - 「發現的問題」以白話文列出具體問題，並提供「查看技術細節」可展開 endpoint／狀態／證據等資訊。
7. 使用報告按鈕開啟完整的 HTML 報告、匯出 JSON／Markdown，或開啟報告所在資料夾。

如果執行過程中發生非預期的錯誤，GUI 只會顯示一則白話文錯誤訊息與一組**錯誤編號**——絕不會顯示原始的 Python 錯誤堆疊、密碼、token 或連線字串。完整的技術細節（已去除機密資訊）只會寫入應用程式自己的記錄檔，不會出現在瀏覽器畫面上。

### 效能測試 API 選擇

勾選「效能測試」後，GUI 會查看專案的 OpenAPI 規格：

- **只有一個可用的 API**——會自動選用，不需要你動手選。
- **有多個候選 API**——會列出 `方法 /路徑` 清單讓你選擇（這份清單是後端直接解析 OpenAPI 規格產生的，瀏覽器本身不會解析規格檔）。
- **找不到 OpenAPI 規格**——GUI 會說明原因，並告訴你可以在進階設定中指定規格檔，或改用 CLI 的 `--endpoint`／`--method` 參數。

### API 驗證設定

在「進階設定」中可以設定要測試的 API 需要的驗證方式：不需要驗證、Bearer Token、API 金鑰，或 Basic 帳號密碼。每一個欄位填的都是**環境變數的名稱**（例如 `API_TOKEN`），絕不是實際的密碼或金鑰內容——GUI 只會在執行測試時讀取該環境變數的值，就跟 CLI 的 `--bearer-token-env` 參數一樣。實際的憑證內容絕不會被儲存、顯示，或寫入任何報告或記錄檔中。

詳細操作說明請見 `docs/GUI_USER_GUIDE.md`，安全保證請見 `docs/GUI_SAFETY.md`，架構說明請見 `docs/GUI_ARCHITECTURE.md`。

## Windows 一鍵執行版

本專案的原始碼儲存庫中並未附上預先建置好的 `UniversalTest.exe`——需要你（或任何人）先在本機從原始碼建置一次。建置完成後，產出的是一個一般的可攜式資料夾，之後可以無限次雙擊執行，不需要再重新建置（除非原始碼有變更）。

**建置一次**（需要 Python 3.11 以上版本，並取得本專案原始碼）：

```powershell
pip install ".[packaging]"
powershell -File release/windows/build.ps1
```

**接著找到並執行它：**

```
dist\windows\UniversalTest\UniversalTest.exe
```

在檔案總管中雙擊 `UniversalTest.exe`（或從終端機執行）。程式會以「無主控台視窗」的方式執行——不會跳出黑色的命令列視窗——並自動開啟你的預設瀏覽器進入 GUI。如果瀏覽器未能自動開啟，畫面上會跳出一個小視窗，顯示本機網址讓你手動開啟。整個 `dist\windows\UniversalTest\` 資料夾都是可攜式的——可以複製到任何地方，或放到隨身碟／其他 Windows 電腦上，`UniversalTest.exe` 在沒有安裝 Python 的機器上依然可以執行。

選用的資料庫驅動程式（PostgreSQL／MySQL／SQL Server）並未一併封裝；缺少驅動程式時，GUI 會回報「資料庫檢查需要額外的資料庫驅動程式」，而不會直接崩潰。

## 指令

### `scan`

唯讀的專案探索：語言、專案類型、框架、建置系統、基礎設施／CI 證據、資料庫證據、API 證據、測試框架，以及潛在密碼／金鑰的**樣式（pattern）**（絕不記錄實際數值）。

```bash
universal-test scan ./my-project
universal-test scan ./my-project --format json --output ./out
```

### `test`

解析 OpenAPI 3.x 文件、產生保守的正向／負向功能性測試案例，並且——只有在提供 `--target` 時——才會透過 HTTP 實際執行這些測試。

```bash
universal-test test ./my-project --dry-run
universal-test test ./my-project --target http://localhost:8000
universal-test test ./my-project --target http://localhost:8000 \
    --bearer-token-env API_TOKEN   # 讀取該環境變數；token 本身不會出現在指令列上
```

`--dry-run` 會顯示將會執行的內容，但不會送出任何 HTTP 請求：

```text
Discovered: 2 endpoints
Generated: 4 test cases

API-001
GET /users
Expected: 200
...
No HTTP requests executed.
```

### `performance`

針對單一 endpoint 執行有界限並行數的負載測試。即使加上 `--dry-run`，`--target` 仍然是必填的——沒有明確目標的效能測試計畫，稱不上是一個計畫。

```bash
universal-test performance ./my-project --target http://localhost:8000 \
    --endpoint /api/users --method GET --dry-run
universal-test performance ./my-project --target http://localhost:8000 \
    --endpoint /api/users --method GET \
    --profile load --concurrency 1,10,50 --requests 100 --yes
```

若未加上 `--dry-run`／`--yes`，工具會印出測試計畫並詢問 `Proceed? [y/N]`，確認後才會送出任何請求。每一個數值型參數（並行數、請求數、持續時間、階段數）都有一個不受設定值影響的硬性安全上限。

### `database`

唯讀的 schema／table／view／column／key／index 評估。**只會**連線到明確設定的資料庫——絕不是單純從專案的相依套件清單中偵測到的那個——且完全沒有任意 SQL 執行的能力。

```yaml
# database.yaml —— 絕不要在檔案中寫入真實憑證，請改用環境變數
database:
  engine: postgresql       # sqlserver | postgresql | mysql | sqlite
  host: localhost
  port: 5432
  database: my_app_dev
  credentials:
    username_env: DB_USER      # 執行時從 $DB_USER 讀取
    password_env: DB_PASSWORD  # 執行時從 $DB_PASSWORD 讀取
  readonly: true            # 必填——省略此欄位（或設為 false）會直接拒絕連線
```

```bash
export DB_USER=readonly_user
export DB_PASSWORD=...
universal-test database ./my-project --database-profile ./database.yaml --dry-run
universal-test database ./my-project --database-profile ./database.yaml
```

`--dry-run` 完全不會開啟任何連線——只會印出計畫內容（引擎、主機、固定的唯讀操作清單、"Mode: READ ONLY"）。缺少對應的資料庫驅動程式（例如 SQL Server 所需的 `pyodbc`）時，結果會降級為 `NOT_ASSESSED` 並附上安裝提示，絕不會導致程式崩潰。

### `browser`（第九階段，新增）

真正的、有邊界的、需要明確授權的瀏覽器／UI 測試（選用套件 `pip install universal-test[browser]`）。預設關閉——即使偵測到前端專案，也不會自動啟動瀏覽器。

```bash
universal-test browser install                                   # 明確、一次性下載瀏覽器執行檔
universal-test browser test ./my-site --target http://localhost:8080 --dry-run
universal-test browser test ./my-site --target http://localhost:8080 --yes
```

不會掃描連接埠、不會猜測目標網址。預設只允許 `localhost`／`127.0.0.1`／`::1`／`file://`；其他網址需要明確加上 `--allow-external`。不會猜測帳號密碼，不會自動授予瀏覽器權限（麥克風／攝影機／地理位置），不會執行任意 JavaScript。詳見 `docs/BROWSER_TESTING.md` 與 `docs/BROWSER_SAFETY.md`（目前為英文文件）。

### `web assess`（第十階段，新增）

專為非工程師設計的一鍵網頁健檢：專案結構分析＋前端靜態分析＋瀏覽器基本操作測試＋報告，不需要理解 `scan`／`assess`／`browser test` 這些各自獨立的指令。這只是套用在**同一個** `assess` 管線之上的安全預設組合——不是第二套引擎——範圍限定於靜態分析與瀏覽器測試（不含效能／資料庫測試）。

```bash
universal-test web assess ./my-site --target http://localhost:8080 --dry-run
universal-test web assess ./my-site --target http://localhost:8080 --yes
universal-test web assess ./my-site   # 未提供目標：只執行靜態分析，瀏覽器測試會顯示「尚未評估」
```

GUI 也提供相同的引導式流程，以「網頁應用程式健檢」卡片呈現：選擇專案後點選「分析專案並產生健檢計畫」，即可看到偵測結果（靜態網站／框架前端／全端網頁應用程式，或「沒有偵測到網頁前端」）以及即將執行與不包含的項目，確認後才會開始執行。詳見 `docs/BROWSER_TESTING.md`（目前為英文文件）。

### `browser scenario`（第十一階段，新增）

明確的、使用者自行定義、可重複執行的多步驟網頁操作流程——例如「先登入，再確認出現儀表板」，而不只是單一的煙霧測試。定義於一個 YAML 檔案中（預設 `universal-test-web.yaml`），不是第二套測試引擎：每個步驟都重複使用 `browser test` 已有的操作／斷言／選擇器。

```bash
universal-test browser scenario list ./my-site
universal-test browser scenario validate ./my-site
universal-test browser scenario run ./my-site --scenario login-smoke --target http://localhost:3000 --dry-run
universal-test browser scenario run ./my-site --scenario login-smoke --target http://localhost:3000 --yes
```

機密資料請使用 `value_env: TEST_PASSWORD`（環境變數的「參照」），絕不在檔案中寫入明文密碼——只有在真正執行時才會解析該環境變數，`list`／`validate`／`--dry-run` 期間絕不解析，報告與記錄中也絕不會出現實際值。步驟會依序執行，一旦某個步驟未通過就會停止；`assess --scenario <id> --target ... --yes` 會將結果併入統一報告中的「網頁情境測試（Web Scenarios）」分類。詳見 `docs/WEB_SCENARIOS.md`（目前為英文文件）。

### `assess`

將探索、功能性測試、效能測試、資料庫、回歸比較的結果整合成一份以證據為基礎的報告：包含整體 `PASS/WARNING/FAIL/UNKNOWN` 狀態、逐分類的發現項目、覆蓋率，以及明確的 Unknown/Not-Assessed（未知／未評估）章節。

```bash
universal-test assess ./my-project
universal-test assess ./my-project --target http://localhost:8000
universal-test assess ./my-project --target http://localhost:8000 --performance --yes
universal-test assess ./my-project --target http://localhost:8000 --browser --yes
universal-test assess ./my-project --database-profile ./database.yaml
universal-test assess ./my-project --format json --output ./reports
```

```text
Overall Status: WARNING
```

```json
{
  "assessment": {
    "overall_status": "warning",
    "categories": [
      {"name": "Functional Health", "status": "not_assessed",
       "reason": "no execution target was provided"},
      {"name": "Performance", "status": "not_assessed",
       "reason": "performance execution was not enabled (pass --performance)"}
    ]
  }
}
```

### `baseline`

基準線（baseline）是探索／功能性／效能／資料庫／評估結果在某一時間點的快照（snapshot）。先儲存一份（例如隨著發布版本一併提交），之後便可以拿之後的執行結果來與它比較。

```bash
universal-test baseline save ./my-project --target http://localhost:8000 --output baseline.json

# ……之後，程式有變更之後……
universal-test baseline compare ./my-project --target http://localhost:8000 --baseline baseline.json
```

`baseline compare` 是**唯讀**的——它絕不會寫入 `baseline.json`，也絕不會執行任何 `assess` 不會執行的動作（功能性測試只在提供 `--target` 時執行；效能測試只在同時提供 `--target --performance` 時執行；資料庫比較只在提供 `--database-profile` 時執行）。它會回報：

- **以測試 ID 為單位的功能性回歸**（例如 `API-002: PASS -> FAIL`），而不只是彙總的通過／失敗數量。
- **效能回歸**，具備方向性判斷（延遲／錯誤率／逾時等指標是「越低越好」，RPS 則是「越高越好」），並採用容忍度（tolerance）機制，避免一般量測雜訊被誤判為回歸。
- **資料庫與探索結果的變化**，一律視為資訊性內容——一張資料表或一項偵測到的技術的出現／消失，只會被回報，絕不會被判定為缺陷。
- **評估分類狀態的轉變**（例如 `Performance: PASS -> FAIL`）。

```yaml
# universal-test.yaml —— 效能回歸的容忍度設定（以下為安全預設值）
regression:
  performance:
    p95_percent: 10          # P95 延遲最多可上升 10% 才會被標記
    p99_percent: 10
    rps_percent: 10           # 吞吐量最多可下降 10% 才會被標記
    error_rate_absolute: 1    # 錯誤率最多可上升 1 個百分點才會被標記
```

### CI/CD

`universal-test assess` 是 CI/CD 的進入點。它會依照確定性的**品質關卡（Quality Gate）**評估「評估結果 + 回歸比較結果」，並回傳一個穩定的 exit code，讓你的 pipeline 可以直接依此判斷。

> **CI 模式不會自動授權網路流量。** `--ci` 只會改變工具的*行為方式*（非互動模式、輸出穩定），它絕不能替代 `--yes`。偵測到 CI 環境（`CI`／`GITHUB_ACTIONS`／`GITLAB_CI`／`JENKINS_URL` 等）也純粹只是提供資訊之用，同樣不會放寬任何安全限制。

```bash
universal-test assess . --ci --yes --target http://localhost:8080 --baseline baseline.json --output reports/
echo "exit code: $?"
```

品質關卡（Quality Gate）政策、exit code 規範，以及 CI 供應商範本，詳見下方「回歸比較」與「安全模型」兩節。

## 設定

專案根目錄下的 `universal-test.yaml` 完全是選用的——若不存在，每個指令都會採用安全的預設值執行。以下為所有可用的設定區塊：

```yaml
performance:
  thresholds:
    p95_ms: 500
    error_rate_percent: 1
    min_rps: 50

regression:
  performance:
    p50_percent: 10
    p90_percent: 10
    p95_percent: 10
    p99_percent: 10
    rps_percent: 10
    error_rate_absolute: 1

quality_gate:
  fail_on:
    regression: [critical, high]
    functional: [failure]
    performance: [threshold]
  warn_on:
    regression: [medium]
    database: [schema_change]
    discovery: [change]

ci:
  retry:
    count: 1   # 無論你如何設定，都會被限制在最多 2 次

database:
  enabled: false   # 僅供參考；實際的資料庫連線一律需要明確提供 --database-profile
```

以上顯示的每一個數值都是**預設值**——只有在你想要變更時才需要寫出對應的鍵值。覆寫其中一個子鍵（例如 `quality_gate.fail_on.regression`）不會影響同一區塊中其他項目的預設值；部分覆寫絕不會悄悄停用該區塊中的其他設定。

## 報告

`assess` 會產出 `report.json`（機器可讀、附帶 schema 版本號、結果具確定性）、`report.md`，以及 `report.html`（可離線開啟，不含任何 CDN 或外部 JavaScript）——預設會同時產出三種格式，輸出至 `./reports/`。

每份報告都包含：整體狀態、附帶證據的逐分類發現項目、覆蓋率、明確的 Unknown/Not-Assessed 章節、回歸比較章節（當有提供 `--baseline` 時）、品質關卡章節，以及明確說明本次評估「未能證明」哪些事項的限制聲明。任何密碼、token、API 金鑰、cookie、Authorization 標頭或連線字串憑證，絕不會出現在任何報告、日誌或例外訊息中——這是由專門的遮罩（redaction）機制強制保證，並在測試套件中針對真實的 HTTP 回應驗證過。

### 如何解讀報告狀態

`PASS`／`WARNING`／`FAIL`／`UNKNOWN`／`NOT_ASSESSED` 各自回答不同的問題，絕不會被混為一談：

- **`WARNING` 不代表「壞掉了」。** 它可能只是代表可測試性上的限制（例如沒有偵測到自動化測試框架）或評估不完整，不必然代表應用程式本身有缺陷。每一項發現都會額外標示 `classification`（`defect`／`testability_gap`／`not_assessed`／`informational`／`execution_failure`），讓你能分辨屬於哪一種。報告與 GUI 中都會另外顯示「應用程式健康度（Application Health）」，它只反映真正「執行過」的項目（功能／效能測試）——顯示綠色代表沒有發現確認的缺陷，即使其他分類因缺少測試工具而顯示 WARNING 也一樣。
- **`NOT_ASSESSED` 既不是 `PASS` 也不是 `FAIL`。** 代表這次執行沒有進行該項評估（例如沒提供目標網址、沒啟用效能測試、沒設定資料庫連線設定），不代表成功或失敗。
- **靜態分析只能偵測「能力」與「證據」，無法證明實際執行時的行為。** 偵測到某個瀏覽器 API、表單或互動元素，只代表程式碼中存在這段內容，不代表實際執行時一定正常運作——這正是為什麼「瀏覽器／UI 執行」與靜態前端分析分開報告：除非你明確加上 `assess --browser --target ... --yes`（或使用 `universal-test browser test`），否則永遠顯示為 `NOT_ASSESSED`。
- **品質關卡 `PASS` 代表沒有任何已設定的關卡規則失敗**，不代表整個應用程式已被驗證正確；**`FAIL`** 代表有一項已設定的條件失敗，詳情列在其下方的發現項目中。

## 回歸比較

使用方式請見上方的 `baseline` 指令說明。以下是將回歸比較結果轉換為 pass/warn/fail 判斷的品質關卡政策：

```yaml
quality_gate:
  fail_on:
    regression: [critical, high]
    functional: [failure]
    performance: [threshold]
  warn_on:
    regression: [medium]
    database: [schema_change]
    discovery: [change]
```

這是預設政策——`UNKNOWN`／`NOT_ASSESSED` 的結果（例如未提供 `--database-profile`）預設不會導致建置失敗，除非你明確加入對應規則，例如 `fail_on: {database: [not_assessed]}`。

**完全無法連線的目標，預設絕不會被視為品質回歸**——詳見下方 exit code 表格。若要讓專案將此情況視為回歸，需明確加入 `fail_on: {functional: [unreachable]}` ／ `{performance: [unreachable]}`。

### Exit code（僅適用於 `assess`）

| 代碼 | 意義 |
|---|---|
| `0` | 品質關卡通過（`WARNING` 等級的結果仍會回傳 `0`——警告不會阻擋建置） |
| `1` | 品質關卡未通過（符合了某條已設定的 `fail_on` 規則） |
| `2` | 設定錯誤（`--format` 錯誤、專案路徑無法讀取、`--baseline` 無法載入或版本不相容） |
| `3` | 基礎設施／執行錯誤（目標完全無法連線） |

其他所有指令（`scan`／`test`／`performance`／`database`／`baseline save`／`baseline compare`）僅使用 `0` 代表成功、`2` 代表 CLI／設定錯誤。

### Pull Request 工作流程

分支保護規則本身由你的 CI 供應商設定，本工具不負責管理：

```text
main 分支  ---------->  universal-test baseline save . --target <url> --output baseline.json
                        （提交 baseline.json；這是獨立、刻意執行的步驟）

feature 分支  ---->  universal-test assess . --ci --yes --target <url> --baseline baseline.json
                        |
                        +-- exit 0/warning  -> 允許合併 PR
                        +-- exit 1          -> 阻擋 PR（回歸／品質關卡失敗）
                        +-- exit 3          -> 基礎設施問題，並非回歸判定
```

**CI 執行品質關卡時，絕不會順帶覆寫 `baseline.json`**——`assess --baseline`／`baseline compare` 只會讀取它。更新基準線必須是刻意執行的獨立步驟（例如由維護者手動觸發的工作，或僅限於 default 分支才會執行的流程）。

### CI 供應商範本

這些是起始範本，不是可直接使用的完整流水線——每一份範本都刻意將「啟動你自己的專案（build/deploy）」這個步驟留白，因為 Universal Test 本身絕不會啟動、建置或部署被評估的專案。每份範本都以單純的 `pip install` 安裝 `universal-test`（不依賴任何供應商 SDK）、依賴 CLI 本身的 exit code 判斷成敗，並且無論成功或失敗都會上傳 `reports/` 作為建置產物：

- [`examples/ci/github-actions/universal-test.yml`](examples/ci/github-actions/universal-test.yml)
- [`examples/ci/gitlab/universal-test.yml`](examples/ci/gitlab/universal-test.yml)
- [`examples/ci/jenkins/Jenkinsfile`](examples/ci/jenkins/Jenkinsfile)

## 安全模型

- **Repository（原始碼儲存庫）**：探索過程完全唯讀。它絕不會修改你的專案、安裝相依套件、啟動容器，或執行專案中的任何腳本（`setup.py`、`package.json` 裡的 scripts、`Makefile`、`Dockerfile`，或 CI 設定檔裡的指令）——本工具唯一會執行的外部程序，是唯讀的 `git rev-parse`／`git status --porcelain`。
- **網路**：沒有明確提供 `--target`，就絕不會送出任何請求。OpenAPI 文件自帶的 `servers:` 欄位絕不會被當作替代目標使用。`scan` 以及沒有 `--target` 的 `assess`，都不會產生任何網路流量。
- **資料庫**：沒有明確提供 `--database-profile`，就絕不會嘗試任何連線，且該設定檔必須明確寫出 `readonly: true`——省略此欄位（或設為 `false`）會直接拒絕連線。整個程式碼庫中沒有任何任意 SQL 執行的 API；每一項資料庫操作都是固定、唯讀的中繼資料（metadata）查詢之一。
- **機密資訊**：憑證只會從你指定的具名環境變數讀取——絕不會從你的 repository 中讀取，也絕不會被寫入任何報告、日誌或例外訊息中。密碼、token、API 金鑰、cookie、Authorization 標頭與連線字串憑證，全部都會被遮罩處理。
- **CI**：`--ci` 與 CI 環境偵測絕不會自行授權網路流量，也不會放寬任何安全限制——真實流量一律需要另外明確提供 `--yes`。已儲存的基準線是不可變的（immutable）；除了 `baseline save`（且只會寫入你明確指定的 `--output` 路徑）之外，沒有任何指令會寫入基準線檔案。CI 重試機制範圍有限且謹慎——它絕不會重試真正的斷言（assertion）或門檻（threshold）失敗，只會重試完全連線失敗（total transport wipeout）的情況。
- **效能測試**：每一個數值型參數（並行數、請求數、持續時間、階段數）都有一個不受你設定值影響的硬性上限。

## 支援的技術

- **探索（Discovery）**：12 種以上程式語言、常見框架（FastAPI、Django、Flask、Express、ASP.NET Core、Spring Boot、Laravel、React、Angular、Vue 等）、Docker／Compose／Kubernetes／GitHub Actions／GitLab CI／Jenkins／Azure Pipelines 證據、6 種資料庫、OpenAPI／Swagger／GraphQL／REST 路由證據、常見測試框架。
- **前端／網頁應用程式分析**：React、Next.js、Vue、Nuxt、Angular、Svelte、SvelteKit、Solid、Astro；Vite／Webpack／Rollup／Turbopack／Angular CLI 建置工具；Jest／Vitest／Mocha／Karma／Jasmine／Testing Library 單元測試框架，以及 Playwright／Cypress／WebdriverIO／Puppeteer 瀏覽器自動化框架；有邊界的路由／元件／表單／API 呼叫證據掃描。**純靜態 HTML／CSS／JavaScript 網站也支援**——不需要 `package.json` 或任何建置工具——包含內嵌／外部 CSS／JS 數量、進入點偵測、導覽連結／表單／API 呼叫／響應式設計／登入介面等結構性證據，以及常見 CSS 框架偵測（Bootstrap／Tailwind／Bulma／Foundation），還有互動元件證據、瀏覽器 API 偵測（麥克風、語音合成、儲存空間、WebSocket 等）、應用程式型態推測（多頁靜態網站／單頁應用程式／靜態文件）、外部資源證據與 CSP 證據，讓單一檔案但內容豐富的網頁應用程式不會被誤判為「沒有 CSS／JS」。靜態探索與可測試性評估一律會執行；瀏覽器／UI 實際執行則是另一項需要明確加上 `--browser` 才會啟動的功能（詳見 [`docs/FRONTEND_ANALYSIS.md`](docs/FRONTEND_ANALYSIS.md) 與 [`docs/BROWSER_TESTING.md`](docs/BROWSER_TESTING.md)，目前為英文文件）。
- **瀏覽器／UI 功能測試**：透過 Playwright 支援 Chromium／Firefox／WebKit（選用套件 `[browser]`）。只能測試明確指定的目標，支援有邊界的 navigate／click／fill／select／check／uncheck／press／wait_for 操作，role／label／text／placeholder／test_id／css 選擇器，以及可見性／文字／網址／標題／元素數量／屬性／輸入值／勾選／啟用／停用等斷言。所有地方預設皆為關閉。
- **功能性／效能測試**：OpenAPI 3.x 規格的 REST API。
- **資料庫評估**：SQL Server、PostgreSQL、MySQL、SQLite。
- **CI**：任何能執行 shell 指令並檢查 exit code 的 CI 系統——GitHub Actions、GitLab CI 與 Jenkins 已提供現成範本。

## 限制

這是一份**初步、自動化的評估**——不是安全稽核，不是正確性證明，也不能取代 QA 或程式碼審查：

- 不能證明軟體是安全的。
- 不能證明軟體沒有錯誤（bug）。
- 不能證明商業邏輯的正確性。
- 不能證明軟體已可上線（production ready）。
- 不能證明測試覆蓋率完整。
- 不是安全掃描工具，也不是弱點偵測工具。
- 不是通用的瀏覽器／UI 自動化框架——瀏覽器測試僅支援一個保守的煙霧測試，加上一組有限、明確的操作／斷言詞彙，不支援任意流程自動化、視覺回歸比對或無障礙稽核。
- 不是 AI 驅動或自主（autonomous）的測試代理人——所有結果皆完全具確定性；本工具中沒有任何 AI／LLM 元件。
- 不是模糊測試（fuzzing）框架——功能性測試是保守的，僅根據文件中明確記載的範例／預設值／schema 產生。
- 不支援 Swagger 2.0 文件（僅支援 OpenAPI 3.x）。
- 目前自動化測試套件中，只有 SQLite 具備真實資料庫的整合測試；SQL Server／PostgreSQL／MySQL 的支援是透過相同的驅動程式介面（driver contract）與「驅動程式缺失」的處理測試來驗證，而非對真實資料庫伺服器測試，因此一般測試套件不需要依賴 Docker。

## 開發

若你想貢獻 Universal Test 本身（而不只是使用它）：

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash；cmd.exe 請用 .venv\Scripts\activate.bat
python -m pip install -e ".[dev]"
python -m pytest -q
```

| 文件 | 用途 |
|---|---|
| `skill.md` | 開發準則（development constitution）——本專案所有規則的最終依據。 |
| `SPECIFICATION.md` | 由 `skill.md` 衍生出的功能需求。 |
| `ARCHITECTURE.md` | 模組邊界、技術選型、Core 介面設計。 |
| `ROADMAP.md` | 各階段（Phase）規劃與目前狀態。 |
| `PROGRESS.md` | 各階段完成內容的紀錄。 |
| `CHANGELOG.md` | 對使用者可見的變更紀錄。 |
| `docs/V1_FREEZE.md` | 已凍結（frozen）的 V1.0 能力／規範範圍。 |
| `docs/V1_HARDENING_AUDIT.md` | 發布前的架構／安全性稽核紀錄。 |
| `docs/V1_RELEASE.md` | V1.0 發布清單（release manifest）。 |
| `docs/POST_V1_BACKLOG.md` | V1 之後的候選方向清單（尚未承諾實作）。 |
| `docs/WEB_CAPABILITY_FREEZE.md` | 已凍結（frozen）的 Web 能力（Phase 9-11）規範範圍——包含／明確不包含項目。 |

### 架構總覽

```text
Universal Core（與技術無關）
   models | engine | assertions | orchestration | configuration
        |
        v
Adapters（技術相關）                          Testing（與技術無關）
   rest | database                             performance | reliability（未來規劃）
   graphql | browser | docker |
   dotnet | node | python（尚未實作）
        |                                             |
        +---------------------+------------------------+
                               v
     Discovery -> Testing -> Assessment -> Reporting -> Regression -> Quality Gate
                                                                          |
                                                                          v
                                                               CI Adapter / Template
                                                          (GitHub Actions / GitLab / Jenkins)
```

Core 絕不會匯入任何與特定技術相關的程式碼；各個 adapter 實作共用的
`detect/describe/discover/generate_tests/execute/collect_metrics` 介面。
`assessment/`／`reporting/` 只會彙整 Discovery／Testing 已經產出的結果——絕不會重新探索或重新執行任何動作。
`regression/` 只會比較兩份已經建立好的快照。
`quality_gate/` 只會針對已經建立好的評估結果與回歸比較結果，依照可設定的政策進行判斷——Core 或本套件中完全沒有任何 GitHub／GitLab／Jenkins／Azure 相關的邏輯；所有與特定供應商相關的內容，都存在於可替換的 `examples/ci/*` 範本中。完整細節請參閱 `ARCHITECTURE.md`。
