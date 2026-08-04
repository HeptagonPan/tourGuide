# tourGuide MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个本地运行的上海旅游规划网页，通过固定问答、可追溯参考价格、高德路线和本地中文模型生成可导出的行程。

**Architecture:** FastAPI 提供页面和 JSON API，Pydantic 负责边界校验，独立服务分别处理参考数据、交通、住宿、预算、高德和文本生成。Jinja2 与原生 JavaScript 构成双栏问答和行程优先结果页；模型仅润色已验证事实，失败时使用确定性模板。

**Tech Stack:** Python 3.12、uv、FastAPI、Pydantic、Jinja2、httpx、原生 CSS/JavaScript、Ollama `qwen2.5:0.5b`、pytest、Ruff。

## Global Constraints

- GitHub 受跟踪文件硬性上限 500MB，目标不超过 100MB。
- `.venv`、Ollama 与默认模型合计不超过 1.5GB。
- Python 必须固定为 3.12，虚拟环境必须是项目根目录 `.venv`。
- VS Code 必须使用 `${workspaceFolder}/.venv/bin/python`。
- Python 标识符使用一致的英文命名；必要注释、文档字符串、界面和 README 使用简体中文。
- 公共函数、服务边界和数据模型必须有类型标注，并通过 Ruff 格式化。
- 模型、密钥、缓存、日志、导出文件和手写需求不得提交。
- 金额在内部统一使用整数“分”，模型不得计算金额或补充事实。
- 每个完整任务通过测试后单独提交并推送 `main`。

## File Map

```text
.env.example                         # 环境变量示例
.github/workflows/ci.yml             # 测试、静态检查与容量检查
.gitignore                           # 本地环境和产物排除
.python-version                      # Python 3.12
.vscode/settings.json                # VS Code 解释器与测试设置
pyproject.toml                       # 依赖与工具配置
uv.lock                              # 锁定依赖
app/main.py                          # FastAPI 工厂和静态资源挂载
app/config.py                        # Settings 与路径
app/api/routes.py                    # 页面、规划和导出接口
app/schemas/trip.py                  # 问卷、路线、预算和行程模型
app/repositories/presets.py          # 预设城市、POI 与参考价格读取
app/services/accommodation.py        # 房间计算
app/services/amap.py                 # 高德 Web 服务适配
app/services/budget.py               # 确定性预算计算
app/services/transport.py            # 大交通候选方案
app/services/planner.py              # 行程编排
app/services/narrator.py             # Ollama 与模板降级
app/services/exporter.py             # 独立 HTML 导出
app/templates/index.html             # 双栏问答页
app/templates/result.html            # 行程优先结果页
app/templates/export.html            # 独立导出模板
app/static/css/app.css                # 响应式日式编辑网格
app/static/images/shanghai-riverside.webp # 轻量上海城市视觉素材
app/static/js/questionnaire.js        # 七步问答与摘要
app/static/js/result.js               # 日期切换和导出
data/presets/cities.json              # 10 个出发城市及枢纽
data/presets/interests.json           # 兴趣选项
data/presets/shanghai_pois.json       # 上海候选 POI
data/reference/prices.json            # 带来源和日期的参考价格
scripts/check_sizes.py                # Git 与本地容量检查
tests/                                # 单元、接口、流程和数据测试
README.md                             # 简体中文使用说明
```

---

### Task 1: 隔离环境与可运行骨架

**Files:**
- Create: `.python-version`
- Create: `.vscode/settings.json`
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/test_health.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI`，`GET /health -> {"status": "ok"}`。

- [ ] **Step 1: 检查工具并创建项目专属环境**

Run:

```bash
command -v uv || brew install uv
uv python install 3.12
uv venv --python 3.12 .venv
```

Expected: `.venv/bin/python --version` 输出 `Python 3.12.x`，不使用 `/opt/homebrew/bin/python3`。

- [ ] **Step 2: 写入项目和 VS Code 配置**

`pyproject.toml` 使用以下完整配置：

```toml
[project]
name = "tour-guide"
version = "0.1.0"
description = "本地运行的上海旅游规划工具"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.116,<1",
  "httpx>=0.28,<1",
  "jinja2>=3.1,<4",
  "pydantic-settings>=2.10,<3",
  "uvicorn[standard]>=0.35,<1",
]

[dependency-groups]
dev = [
  "pytest>=8.4,<9",
  "pytest-asyncio>=1.1,<2",
  "respx>=0.22,<1",
  "ruff>=0.12,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
```

`.vscode/settings.json` 固定：

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.analysis.typeCheckingMode": "basic"
}
```

`.env.example` 固定包含空的 `AMAP_WEB_KEY`、可选 `AMAP_JS_KEY`、`OLLAMA_BASE_URL=http://127.0.0.1:11434` 和 `OLLAMA_MODEL=qwen2.5:0.5b`。`.gitignore` 排除 `.venv/`、`.env`、`cache/`、`logs/`、`exports/`、模型格式和 macOS 元数据。

- [ ] **Step 3: 安装并锁定依赖**

Run:

```bash
uv sync --dev
uv lock --check
```

Expected: `.venv` 与 `uv.lock` 生成，`uv run python --version` 为 3.12.x。

- [ ] **Step 4: 写失败的健康检查测试**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Run: `uv run pytest tests/test_health.py -v`

Expected: FAIL，因为 `app.main` 尚未实现。

- [ ] **Step 5: 实现最小 FastAPI 工厂**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    """创建本地 Web 应用。"""
    app = FastAPI(title="tourGuide")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 6: 验证并提交**

Run: `uv run pytest tests/test_health.py -v && uv run ruff check . && uv run ruff format --check .`

Expected: 全部通过。

Commit: `chore: initialize isolated Python application`

---

### Task 2: 配置、问卷模型与预设数据

**Files:**
- Create: `app/config.py`
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/trip.py`
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/presets.py`
- Create: `data/presets/cities.json`
- Create: `data/presets/interests.json`
- Create: `tests/test_trip_schemas.py`
- Create: `tests/test_presets.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: `Settings`、`TripRequest`、`TravelPreference`、`PresetRepository.load_cities()`、`PresetRepository.load_interests()`。

- [ ] **Step 1: 写输入校验失败测试**

```python
import pytest
from pydantic import ValidationError

from app.schemas.trip import TripRequest


def test_trip_request_rejects_unsupported_origin(valid_request_data: dict) -> None:
    valid_request_data["origin_city"] = "东京"

    with pytest.raises(ValidationError):
        TripRequest.model_validate(valid_request_data)


def test_trip_request_rejects_reversed_dates(valid_request_data: dict) -> None:
    valid_request_data["start_date"] = "2026-10-05"
    valid_request_data["end_date"] = "2026-10-02"

    with pytest.raises(ValidationError):
        TripRequest.model_validate(valid_request_data)
```

Run: `uv run pytest tests/test_trip_schemas.py -v`

Expected: FAIL，因为模型尚不存在。

- [ ] **Step 2: 实现有类型的问卷模型**

`TripRequest` 固定字段：`origin_city`、`adults`、`children`、`rooms`、`relationship`、`start_date`、`end_date`、`budget_cents`、`budget_includes_intercity`、`interests`、`intercity_preference`、`local_transport_preference`。

校验规则：城市必须来自 10 个预设值；成人至少 1；房间至少 1 且不超过总人数；结束日期不得早于开始日期；旅行 1–14 天；预算至少 100 元；兴趣至少选择 1 项。

`tests/conftest.py` 提供 `valid_request_data`、`request_factory`、`repository`、`sample_plan` 和注入假服务的 `client`，后续测试统一复用这些稳定夹具。

- [ ] **Step 3: 写预设数据完整性失败测试**

```python
def test_city_presets_have_exact_supported_names(repository) -> None:
    names = {city.name for city in repository.load_cities()}

    assert names == {
        "合肥", "芜湖", "蚌埠", "淮南", "阜阳",
        "安庆", "黄山", "马鞍山", "滁州", "南京",
    }
```

Run: `uv run pytest tests/test_presets.py -v`

Expected: FAIL，因为预设仓库尚不存在。

- [ ] **Step 4: 实现 JSON 预设仓库和数据**

每个城市记录 `name`、`province`、`railway_stations`、`nearby_airports`；兴趣记录 `id`、`label`、`poi_categories`。路径由 `Settings.project_root` 组合，不依赖当前工作目录。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_trip_schemas.py tests/test_presets.py -v && uv run ruff check .`

Expected: 全部通过。

Commit: `feat: add validated questionnaire presets`

---

### Task 3: 可追溯参考价格仓库

**Files:**
- Modify: `app/schemas/trip.py`
- Modify: `app/repositories/presets.py`
- Create: `data/reference/prices.json`
- Create: `tests/test_reference_prices.py`

**Interfaces:**
- Produces: `ReferencePrice`、`PresetRepository.load_reference_prices()`、`find_prices(category, origin_city=None)`。

- [ ] **Step 1: 写来源完整性失败测试**

```python
from datetime import date


def test_every_reference_price_is_traceable(repository) -> None:
    records = repository.load_reference_prices()

    assert records
    for record in records:
        assert record.source_url.startswith("https://")
        assert record.observed_at <= date.today()
        assert record.price_min_cents >= 0
        assert record.price_max_cents >= record.price_min_cents
```

再写参数化测试，保证 10 个城市各有至少一个到上海的 `rail` 记录，并且酒店包含经济、舒适和品质三个档位。

Run: `uv run pytest tests/test_reference_prices.py -v`

Expected: FAIL，因为数据和读取方法尚不存在。

- [ ] **Step 2: 人工核验最小参考数据集**

使用携程公开搜索页面逐条查看，不编写抓取程序。记录页面链接、查看日期、适用日期和价格区间；交通至少覆盖 10 个城市到上海的高铁，住宿覆盖上海三个档位，景点仅记录明确收费项目。所有价格保存为整数分。

- [ ] **Step 3: 实现严格读取与查询**

JSON 解析后必须通过 `ReferencePrice` 校验。重复 `id`、未知类别、无来源链接、负价格或日期倒置时抛出带简体中文说明的 `PresetDataError`。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_reference_prices.py -v && uv run ruff check .`

Expected: 全部通过且没有缺少来源的记录。

Commit: `feat: add traceable travel reference prices`

---

### Task 4: 住宿、大交通与预算引擎

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/accommodation.py`
- Create: `app/services/transport.py`
- Create: `app/services/budget.py`
- Modify: `app/schemas/trip.py`
- Create: `tests/test_accommodation.py`
- Create: `tests/test_transport.py`
- Create: `tests/test_budget.py`

**Interfaces:**
- Produces: `calculate_default_rooms(request: TripRequest) -> int`、`build_transport_options(request, repository) -> list[TransportOption]`、`calculate_budget(request, transport, accommodation, daily_costs) -> BudgetBreakdown`。

- [ ] **Step 1: 写住宿规则失败测试**

```python
def test_couple_defaults_to_one_room(request_factory) -> None:
    request = request_factory(adults=2, relationship="couple", rooms=None)

    assert calculate_default_rooms(request) == 1


def test_friends_default_to_separate_rooms(request_factory) -> None:
    request = request_factory(adults=2, relationship="friends", rooms=None)

    assert calculate_default_rooms(request) == 2
```

Run: `uv run pytest tests/test_accommodation.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现住宿默认值和用户覆盖**

不读取性别。`rooms` 有值时使用用户值；无值时夫妻或伴侣为 1 间，其他成人按每人 1 间，儿童不单独增加房间。

- [ ] **Step 3: 写交通与预算失败测试**

```python
def test_budget_uses_integer_cents(valid_request, repository) -> None:
    options = build_transport_options(valid_request, repository)
    result = calculate_budget(
        request=valid_request,
        transport=options[0],
        accommodation_cents=160_000,
        dining_cents=80_000,
        attraction_cents=20_000,
        local_transport_cents=12_000,
    )

    assert result.total_cents == sum(result.categories.values())
    assert result.remaining_cents == valid_request.budget_cents - result.total_cents
```

添加淮南经合肥机场的多段成本相加测试，以及预算不足时 `is_over_budget is True` 的测试。

Run: `uv run pytest tests/test_transport.py tests/test_budget.py -v`

Expected: FAIL。

- [ ] **Step 4: 实现交通候选与预算引擎**

交通候选只由参考记录和城市枢纽组合；每段保留 `source_ids`。预算分类固定为 `intercity`、`accommodation`、`dining`、`attractions`、`local_transport`、`reserve`，备用金取已知支出的 10%，使用整数运算。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_accommodation.py tests/test_transport.py tests/test_budget.py -v && uv run ruff check .`

Expected: 全部通过。

Commit: `feat: add deterministic travel budget services`

---

### Task 5: 高德 Web 服务适配

**Files:**
- Create: `app/services/amap.py`
- Modify: `app/config.py`
- Create: `tests/test_amap.py`
- Create: `tests/fixtures/amap_transit.json`

**Interfaces:**
- Produces: `AmapClient.search_pois()`、`AmapClient.get_route()`、`AmapClient.get_weather()`；全部返回项目内部 Pydantic 模型。

- [ ] **Step 1: 写正常响应、超时和错误码测试**

```python
@pytest.mark.asyncio
async def test_get_route_normalizes_amap_response(amap_client, respx_mock) -> None:
    respx_mock.get(path="/v5/direction/transit/integrated").mock(
        return_value=httpx.Response(200, json=AMAP_TRANSIT_FIXTURE)
    )

    route = await amap_client.get_route(origin="121.47,31.23", destination="121.49,31.24")

    assert route.source == "amap"
    assert route.duration_minutes > 0
    assert route.steps
```

另写第一次超时、第二次成功的重试测试，以及两次失败后抛出 `AmapUnavailableError` 的测试。

Run: `uv run pytest tests/test_amap.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现密钥配置和异步客户端**

`Settings.amap_web_key` 从 `.env` 读取。客户端设置明确超时，只对连接错误、超时和 5xx 重试一次；高德业务错误不重复请求。日志不得包含完整 Key。

- [ ] **Step 3: 实现响应归一化**

将高德秒、米和字符串费用转换为分钟、米和整数分。原始响应不得传给模型；每个归一化对象保留 `source="amap"` 和查询时间。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_amap.py -v && uv run ruff check .`

Expected: 全部通过，测试不调用真实高德接口。

Commit: `feat: add resilient Amap service adapter`

---

### Task 6: 上海行程编排与模型降级

**Files:**
- Create: `data/presets/shanghai_pois.json`
- Create: `app/services/planner.py`
- Create: `app/services/narrator.py`
- Modify: `app/schemas/trip.py`
- Create: `tests/test_planner.py`
- Create: `tests/test_narrator.py`

**Interfaces:**
- Produces: `async Planner.generate(request: TripRequest) -> TripPlan`、`async Narrator.describe(plan: TripPlan) -> str`。

- [ ] **Step 1: 写行程规则失败测试**

测试每一天最多 4 个主要活动、同一区域优先、活动之间存在路线、所有费用含来源 ID，以及总预算等于预算引擎结果。

Run: `uv run pytest tests/test_planner.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现候选 POI 与确定性编排**

POI 数据包含高德名称、区域、兴趣标签、建议停留分钟、收费参考 ID。编排先按兴趣过滤，再按行政区域分组，按天分配上午、午餐、下午和晚间槽位；无法验证路线的相邻活动不得加入最终计划。

- [ ] **Step 3: 写模型失败降级测试**

```python
@pytest.mark.asyncio
async def test_narrator_falls_back_without_changing_facts(plan, failing_http_client) -> None:
    narrator = Narrator(http_client=failing_http_client)

    text = await narrator.describe(plan)

    assert plan.destination in text
    assert f"¥{plan.budget.total_cents / 100:,.0f}" in text
    assert "暂未连接本地模型" not in text
```

Run: `uv run pytest tests/test_narrator.py -v`

Expected: FAIL。

- [ ] **Step 4: 实现 Ollama 适配和固定模板**

只向 `http://127.0.0.1:11434/api/chat` 发送经过序列化的 `TripPlan`。系统提示明确禁止增加名称、数字和路线；响应为空、超时或不可解析时使用模板。模板语气客观、直接、略微轻松。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_planner.py tests/test_narrator.py -v && uv run ruff check .`

Expected: 全部通过。

Commit: `feat: generate grounded Shanghai itineraries`

---

### Task 7: 页面 API 与独立 HTML 导出

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/routes.py`
- Modify: `app/main.py`
- Create: `app/services/exporter.py`
- Create: `app/templates/export.html`
- Create: `tests/test_api.py`
- Create: `tests/test_exporter.py`

**Interfaces:**
- Produces: `GET /`、`GET /api/options`、`POST /api/plans`、`POST /api/export`。

- [ ] **Step 1: 写 API 合同失败测试**

```python
def test_create_plan_returns_grounded_plan(client, valid_request_data) -> None:
    response = client.post("/api/plans", json=valid_request_data)

    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == "上海"
    assert body["days"]
    assert body["source_ids"]
```

另测 422 输入错误为简体中文，外部服务失败返回 503 且不含密钥和堆栈。

Run: `uv run pytest tests/test_api.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现依赖注入和路由**

应用工厂接收可选服务对象，测试注入假高德和假模型。生产环境在请求级构建规划器；`/api/options` 返回城市、兴趣和交通选项。

- [ ] **Step 3: 写独立导出失败测试**

断言导出响应为 `text/html`，包含完整预算和每日行程，不引用 localhost 静态资源，不包含 API Key。

Run: `uv run pytest tests/test_exporter.py -v`

Expected: FAIL。

- [ ] **Step 4: 实现自包含 HTML 导出**

CSS 内联到导出模板；地图退化为带来源说明的路线文字。文件名使用 `tourGuide-上海-YYYYMMDD.html`，响应通过 `Content-Disposition` 下载。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_api.py tests/test_exporter.py -v && uv run ruff check .`

Expected: 全部通过。

Commit: `feat: expose planning and HTML export APIs`

---

### Task 8: 双栏固定问答界面

**Files:**
- Create: `app/templates/index.html`
- Create: `app/static/css/app.css`
- Create: `app/static/images/shanghai-riverside.webp`
- Create: `app/static/js/questionnaire.js`
- Modify: `app/main.py`
- Modify: `app/api/routes.py`
- Create: `tests/test_index_page.py`

**Interfaces:**
- Consumes: `GET /api/options`、`POST /api/plans`。
- Produces: 七步问答、右侧实时摘要、加载状态、简体中文错误状态。

- [ ] **Step 1: 写页面结构失败测试**

```python
def test_index_contains_questionnaire_shell(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="questionnaire"' in response.text
    assert 'id="trip-summary"' in response.text
    assert 'lang="zh-CN"' in response.text
```

Run: `uv run pytest tests/test_index_page.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现语义化双栏布局**

左侧一次显示一个问题，右侧固定显示已确认摘要；桌面双栏、手机单栏。所有输入都有 `<label>`，进度使用 `aria-valuenow`，错误区域使用 `aria-live="polite"`。

- [ ] **Step 3: 实现七步状态机**

JavaScript 使用单一 `tripDraft` 对象，字段名与 `TripRequest` 完全一致。每步进入前校验当前字段；支持返回修改；提交期间禁用按钮，失败时保留输入。

- [ ] **Step 4: 实现已确认视觉方向**

采用炭黑、玉绿、少量信号红；使用非对称日式编辑网格、细线、留白和少量竖排标签。卡片圆角不超过 4px，不使用渐变、装饰光球或大面积营销式 Hero。

通过 ImageGen 生成一张清晰展示上海外滩与浦东天际线的横向位图，转换为 WebP 并压缩到 500KB 以下；它作为问答欢迎状态和结果概览的上海信号，不替代路线地图，也不使用版权不明的网络图片。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_index_page.py -v && uv run ruff check .`

Expected: 全部通过。

Commit: `feat: build guided travel questionnaire`

---

### Task 9: 行程优先结果页与响应式交互

**Files:**
- Create: `app/templates/result.html`
- Create: `app/static/js/result.js`
- Modify: `app/static/css/app.css`
- Modify: `app/api/routes.py`
- Create: `tests/test_result_page.py`

**Interfaces:**
- Consumes: `TripPlan` JSON。
- Produces: 日期切换、每日时间线、路线侧栏、大交通比较、住宿与预算、导出按钮。

- [ ] **Step 1: 写结果页内容失败测试**

```python
def test_result_page_renders_budget_and_sources(client, sample_plan) -> None:
    response = client.post("/result", json=sample_plan.model_dump(mode="json"))

    assert response.status_code == 200
    assert "预算明细" in response.text
    assert "参考价格" in response.text
    assert "数据更新时间" in response.text
```

Run: `uv run pytest tests/test_result_page.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现行程优先双栏**

主栏按天呈现时间、地点、停留时间、交通和费用；侧栏显示当天路线摘要和高德来源。下方使用非嵌套的全宽分区展示大交通、住宿和预算。

- [ ] **Step 3: 实现日期切换和导出**

日期标签使用 `button` 和 `aria-selected`；切换只改变可见当天，不重新请求 API。导出按钮提交当前完整计划到 `/api/export`。

- [ ] **Step 4: 验证移动端约束**

CSS 在 760px 以下改为单栏；固定格式元素使用稳定网格和最小宽度；长中文、金额和按钮文字不得溢出或覆盖。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_result_page.py -v && uv run ruff check .`

Expected: 全部通过。

Commit: `feat: render responsive itinerary results`

---

### Task 10: 容量、端到端验证、README 与持续集成

**Files:**
- Create: `scripts/check_sizes.py`
- Create: `tests/test_size_checker.py`
- Create: `tests/test_end_to_end.py`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `uv run python scripts/check_sizes.py`、完整简体中文使用说明、GitHub Actions 验证。

- [ ] **Step 1: 写容量检查失败测试**

测试临时 Git 文件清单超过 500MB 时退出码为 1；正常小仓库为 0；解析 `ollama list` 的 MB/GB 单位并在项目环境合计超过 1.5GB 时失败。

Run: `uv run pytest tests/test_size_checker.py -v`

Expected: FAIL。

- [ ] **Step 2: 实现容量检查脚本**

Git 容量只统计 `git ls-files`；本地容量统计 `.venv` 和默认 Ollama 模型大小，不统计其他项目模型。输出简体中文明细和上限。

- [ ] **Step 3: 写完整流程测试**

使用固定问卷、假高德和假模型执行：加载选项、生成计划、渲染结果、导出 HTML。断言每个价格和路线都有来源 ID，模型失败时流程仍成功。

Run: `uv run pytest tests/test_end_to_end.py -v`

Expected: PASS only after all earlier tasks exist.

- [ ] **Step 4: 编写简体中文 README**

README 必须包含：项目说明、功能边界、目录结构、容量限制、`uv` 环境安装、VS Code 解释器、`.env`、高德 Key、Ollama 安装与 `qwen2.5:0.5b` 下载、运行、测试、导出、数据更新和来源维护规则。

- [ ] **Step 5: 添加持续集成**

GitHub Actions 使用 Python 3.12 和 `uv sync --locked --dev`，依次运行：

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python scripts/check_sizes.py --git-only
```

- [ ] **Step 6: 安装本地模型并验证容量**

Run:

```bash
command -v ollama || brew install ollama
ollama pull qwen2.5:0.5b
uv run python scripts/check_sizes.py
```

Expected: Git 文件小于 500MB，本地项目环境与默认模型合计小于 1.5GB。

- [ ] **Step 7: 启动并进行浏览器验收**

Run: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`

在 1440×900、1024×768、390×844 三个视口完成问卷、生成结果、切换日期和导出。检查无重叠、无横向溢出、地图区域非空、中文提示完整，并保存验证截图到本地临时目录而非仓库。

- [ ] **Step 8: 全量验证并提交**

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python scripts/check_sizes.py
git status --short
```

Expected: 格式、静态检查、全部测试和两项容量检查通过；Git 状态只包含本任务计划提交的文件。

Commit: `docs: finalize tourGuide setup and verification`
