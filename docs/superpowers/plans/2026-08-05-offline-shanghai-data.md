# Offline Shanghai Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用随仓库分发的 SQLite 景点与路线数据替换运行时高德调用，使 tourGuide 在没有地图 Key 和外部网络时仍能生成上海行程。

**Architecture:** `OfflineRepository` 以只读方式查询 `data/offline/shanghai.db`，`OfflineRouteService` 在稀疏路线图上计算直接路线或最短时间路径，`Planner` 使用本地景点和路线生成现有 `TripPlan`。数据库由可审查的 JSON 种子数据和确定性构建脚本生成，现有问卷、预算、住宿、结果页和导出接口保持兼容。

**Tech Stack:** Python 3.12、标准库 `sqlite3` 与 `heapq`、FastAPI、Pydantic、Jinja2、原生 JavaScript/CSS、pytest、Ruff。

## Global Constraints

- 运行时不得调用高德或其他地图 API，也不得要求 `AMAP_WEB_KEY`。
- 数据库固定为 `data/offline/shanghai.db`，网页运行期间只读。
- 数据库包含 60 个精选景点，覆盖现有 6 类兴趣和主要上海城区。
- 路线只提供交通方式、预计时间、近似距离、预计费用和主要线路摘要，不冒充实时导航。
- 不保存真实地图瓦片，结果页只显示离线路线示意。
- 不新增数据库服务器、图数据库或 NetworkX 依赖。
- Git 跟踪文件硬性上限为 500MB；本地环境目标不超过 1.5GB。
- 必要注释、文档字符串、错误提示和 README 使用简体中文。
- 每修改完一个代码文件或测试代码文件，立即停止当前轮次，等待用户继续、Fork 或 Redo。不得在同一轮编辑第二个代码文件。
- JSON、SQL、SQLite 和 Markdown 文件也采用单文件检查点，便于用户精确回退。

## File Map

```text
app/schemas/offline.py                    # 离线景点、路线边、路径和元数据模型
app/repositories/offline.py               # 只读 SQLite 查询与数据库版本检查
app/services/offline_routes.py            # 稀疏图与 Dijkstra 路线计算
app/services/planner.py                    # 使用本地景点和路线生成 TripPlan
app/api/routes.py                          # 默认装配离线仓库与路线服务
app/static/js/result.js                    # 离线路线文字和简化坐标示意
app/static/css/app.css                     # 路线示意与响应式样式
app/templates/export.html                  # 离线路线来源措辞
data/offline/shanghai_seed.json            # 60 个景点、来源、兴趣和路线边
data/offline/shanghai.db                   # 确定性生成的只读 SQLite 数据库
scripts/build_offline_db.py                # 建库、约束和种子导入
tests/test_offline_schemas.py              # 离线数据模型校验
tests/test_offline_builder.py              # 建库完整性与确定性
tests/test_offline_repository.py           # 只读查询与错误处理
tests/test_offline_routes.py               # 直接边、最短路径和断开图
tests/test_planner.py                       # 完全离线行程编排
tests/test_api.py                           # 无 Key 默认 API 装配
tests/test_end_to_end.py                    # 禁止外部 HTTP 的完整流程
tests/test_frontend.py                      # 离线措辞和路线示意 DOM 契约
.env.example                                # 将高德配置改为非必需兼容项
README.md                                   # 离线运行、数据来源和维护方式
```

---

### Task 1: 离线领域模型

**Files:**
- Create: `tests/test_offline_schemas.py`
- Create: `app/schemas/offline.py`

**Interfaces:**
- Consumes: Python `date`、Pydantic `BaseModel` 与 `Field`。
- Produces: `OfflinePoi`、`OfflineRouteEdge`、`OfflineRoutePath`、`OfflineMetadata`。

- [ ] **Step 1: 创建模型失败测试，然后停止当前轮次**

```python
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.offline import OfflinePoi, OfflineRouteEdge


def test_offline_poi_rejects_missing_interest() -> None:
    with pytest.raises(ValidationError):
        OfflinePoi(
            id="the-bund",
            name="外滩",
            district="黄浦区",
            area="外滩与南京东路",
            longitude=121.4901,
            latitude=31.2415,
            suggested_duration_minutes=90,
            admission_cents=0,
            opening_note="开放区域以现场公告为准",
            is_general_highlight=True,
            interests=[],
            source_id="osm-and-official-the-bund",
            verified_at=date(2026, 8, 5),
        )


def test_route_edge_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        OfflineRouteEdge(
            origin_poi_id="the-bund",
            destination_poi_id="nanjing-road",
            transport_mode="walk",
            duration_minutes=-1,
            distance_meters=900,
            cost_cents=0,
            summary="沿南京东路步行",
            is_bidirectional=True,
            source_id="manual-route-estimate",
            verified_at=date(2026, 8, 5),
        )
```

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `uv run pytest tests/test_offline_schemas.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.offline'`。

- [ ] **Step 3: 创建模型文件，然后停止当前轮次**

`app/schemas/offline.py` 定义：

```python
class OfflinePoi(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    district: str = Field(min_length=1)
    area: str = Field(min_length=1)
    longitude: float = Field(ge=120.8, le=122.2)
    latitude: float = Field(ge=30.6, le=31.9)
    suggested_duration_minutes: int = Field(ge=30, le=480)
    admission_cents: int = Field(ge=0)
    opening_note: str = Field(min_length=1)
    is_general_highlight: bool = False
    interests: list[str] = Field(min_length=1)
    source_id: str = Field(min_length=1)
    verified_at: date


class OfflineRouteEdge(BaseModel):
    origin_poi_id: str = Field(min_length=1)
    destination_poi_id: str = Field(min_length=1)
    transport_mode: Literal["walk", "metro", "bus", "mixed"]
    duration_minutes: int = Field(ge=1)
    distance_meters: int = Field(ge=1)
    cost_cents: int = Field(ge=0)
    summary: str = Field(min_length=1)
    is_bidirectional: bool = True
    source_id: str = Field(min_length=1)
    verified_at: date


class OfflineRoutePath(BaseModel):
    origin_poi_id: str
    destination_poi_id: str
    edges: list[OfflineRouteEdge] = Field(min_length=1)
    duration_minutes: int = Field(ge=1)
    distance_meters: int = Field(ge=1)
    cost_cents: int = Field(ge=0)
    instructions: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class OfflineMetadata(BaseModel):
    schema_version: int = Field(ge=1)
    data_version: str = Field(min_length=1)
    generated_at: datetime
    poi_count: int = Field(ge=1)
    route_edge_count: int = Field(ge=1)
```

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_offline_schemas.py -v && uv run ruff check app/schemas/offline.py tests/test_offline_schemas.py && uv run ruff format --check app/schemas/offline.py tests/test_offline_schemas.py`

Commit: `feat: define offline Shanghai data models`

---

### Task 2: 确定性 SQLite 构建

**Files:**
- Create: `tests/test_offline_builder.py`
- Create: `data/offline/shanghai_seed.json`
- Create: `scripts/build_offline_db.py`
- Generate: `data/offline/shanghai.db`

**Interfaces:**
- Consumes: `shanghai_seed.json` 中的 `metadata`、`sources`、`interests`、`pois`、`poi_interests` 和 `route_edges`。
- Produces: `build_database(seed_path: Path, output_path: Path) -> None` 和 schema version `1` 的 SQLite 文件。

- [ ] **Step 1: 创建构建器失败测试，然后停止当前轮次**

测试必须调用 `build_database()`，启用 `PRAGMA foreign_keys = ON`，并断言：

```python
assert connection.execute("SELECT COUNT(*) FROM pois").fetchone()[0] == 60
assert connection.execute("SELECT COUNT(*) FROM interests").fetchone()[0] == 6
assert connection.execute("SELECT COUNT(*) FROM route_edges").fetchone()[0] >= 90
assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
assert connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "1"
```

测试还要构建两份数据库，并比较完整 `iterdump()` 内容相同。`generated_at` 必须来自种子文件中的固定 UTC 时间，不得在构建时读取系统当前时间。

- [ ] **Step 2: 运行测试并确认因构建模块不存在而失败**

Run: `uv run pytest tests/test_offline_builder.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_offline_db'`。

- [ ] **Step 3: 创建种子数据文件，然后停止当前轮次**

`shanghai_seed.json` 必须包含以下恰好 60 个景点，不用高德响应作为公开数据来源：

```text
黄浦区：上海博物馆（人民广场馆）、外滩、南京路步行街、豫园、上海城隍庙、新天地、中共一大纪念馆、人民公园、上海城市规划展示馆、外滩源
浦东新区：东方明珠、上海中心观光厅、金茂大厦观光厅、上海环球金融中心观光厅、陆家嘴滨江步道、世纪公园、上海科技馆、上海海洋水族馆、浦东美术馆、前滩休闲公园
静安区：四行仓库抗战纪念馆、苏州河步道、张园、静安寺、上海自然博物馆、M50创意园、大宁公园、上海马戏城
徐汇区：武康路历史文化名街、徐家汇书院、西岸滨江、上海植物园、龙华寺、徐汇滨江、上海电影博物馆、衡山路
长宁区：上海动物园、中山公园、愚园路、上生新所、刘海粟美术馆、虹桥公园
虹口与杨浦：鲁迅公园、上海邮政博物馆、北外滩、上海犹太难民纪念馆、杨浦滨江、上海共青森林公园、复旦大学江湾校区、江湾体育场
近郊：七宝古镇、闵行文化公园、广富林文化遗址、辰山植物园、佘山国家森林公园、上海影视乐园、嘉定古城、古猗园、朱家角古镇、上海大观园
```

每个景点必须包含稳定 ID、坐标、区域、片区、1–3 个兴趣、时长、费用、开放提示、来源和核验日期。来源至少包含 OpenStreetMap ODbL 归属、上海文旅、上海地铁以及场馆官方网站。路线边优先连接同片区景点，再使用主要地铁线路连接片区枢纽；至少 90 条边，所有边端点必须存在。

- [ ] **Step 4: 创建构建脚本，然后停止当前轮次**

`scripts/build_offline_db.py` 使用事务创建 `sources`、`interests`、`pois`、`poi_interests`、`route_edges` 和 `metadata`。表必须含外键、唯一约束和数值 `CHECK`；导入前删除临时输出，成功后以 `Path.replace()` 原子替换目标数据库。CLI 固定为：

```bash
uv run python scripts/build_offline_db.py \
  --seed data/offline/shanghai_seed.json \
  --output data/offline/shanghai.db
```

- [ ] **Step 5: 生成数据库并验证**

Run: `uv run python scripts/build_offline_db.py --seed data/offline/shanghai_seed.json --output data/offline/shanghai.db`

Run: `uv run pytest tests/test_offline_builder.py -v`

Expected: 60 个景点、6 个兴趣、至少 90 条路线边、无外键错误、重复构建结果一致。

- [ ] **Step 6: 提交**

Commit: `feat: add curated offline Shanghai database`

---

### Task 3: 只读离线仓库

**Files:**
- Create: `tests/test_offline_repository.py`
- Create: `app/repositories/offline.py`

**Interfaces:**
- Consumes: schema version `1` 的 `shanghai.db` 与 Task 1 模型。
- Produces: `OfflineDataError`、`OfflineRepository(database_path: Path)`、`list_pois(interests: Collection[str]) -> list[OfflinePoi]`、`get_poi(poi_id: str) -> OfflinePoi`、`list_route_edges() -> list[OfflineRouteEdge]`、`get_metadata() -> OfflineMetadata`。

- [ ] **Step 1: 创建仓库失败测试，然后停止当前轮次**

测试覆盖：只读 URI `mode=ro`、兴趣筛选无重复、未知景点抛出 `OfflineDataError`、缺失数据库抛出简体中文错误、schema version 非 `1` 被拒绝。

```python
repository = OfflineRepository(PROJECT_ROOT / "data/offline/shanghai.db")
pois = repository.list_pois({"culture", "food"})
assert pois
assert len({poi.id for poi in pois}) == len(pois)
assert all({"culture", "food"}.intersection(poi.interests) for poi in pois)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/test_offline_repository.py -v`

Expected: FAIL because `app.repositories.offline` does not exist。

- [ ] **Step 3: 创建仓库实现，然后停止当前轮次**

仓库使用以下连接形式，所有查询参数化：

```python
uri = f"file:{database_path.resolve()}?mode=ro"
connection = sqlite3.connect(uri, uri=True)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")
```

`list_pois()` 通过 `poi_interests` 聚合兴趣，按 `district, area, name` 稳定排序；模型构造前把逗号拼接结果拆为列表。所有 `sqlite3.Error` 转换为不含路径和 SQL 的 `OfflineDataError`。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_offline_repository.py -v`

Commit: `feat: query offline Shanghai data`

---

### Task 4: 本地稀疏路线图

**Files:**
- Create: `tests/test_offline_routes.py`
- Create: `app/services/offline_routes.py`

**Interfaces:**
- Consumes: `OfflineRepository.list_route_edges()` 与 `OfflineRouteEdge`。
- Produces: `OfflineRouteService(repository: OfflineRepository)`、`find_route(origin_poi_id: str, destination_poi_id: str) -> OfflineRoutePath | None`。

- [ ] **Step 1: 创建路线失败测试，然后停止当前轮次**

使用内存假仓库覆盖：直接边、反向复用、A→B→C 最短时间路径、循环图、断开图和同一端点。核心断言：

```python
path = service.find_route("a", "c")
assert path is not None
assert [edge.destination_poi_id for edge in path.edges] == ["b", "c"]
assert path.duration_minutes == 25
assert path.instructions == ["步行至 B", "乘坐地铁 2 号线至 C"]
assert service.find_route("a", "missing") is None
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/test_offline_routes.py -v`

Expected: FAIL because `app.services.offline_routes` does not exist。

- [ ] **Step 3: 创建路线服务，然后停止当前轮次**

使用 `heapq` 按 `duration_minutes` 作为首要权重、`distance_meters` 作为次要权重。双向边在内存中创建反向副本；返回路径汇总时间、距离、费用、每段 `summary` 和去重来源 ID。同一景点到自身返回 `None`，找不到路径返回 `None`。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_offline_routes.py -v`

Commit: `feat: calculate offline Shanghai routes`

---

### Task 5: 规划器切换为完全离线

**Files:**
- Modify: `tests/test_planner.py`
- Modify: `app/services/planner.py`

**Interfaces:**
- Consumes: `PresetRepository`、`OfflineRepository`、`OfflineRouteService`。
- Produces: `Planner(repository, offline_repository, route_service)`；`generate(request: TripRequest) -> TripPlan` 保持不变。

- [ ] **Step 1: 将规划测试改为离线契约，然后停止当前轮次**

删除 `FakeAmapClient`，使用真实离线仓库和路线服务。测试断言：

```python
assert all(
    source_id.startswith(("offline-poi:", "offline-route:", "rail-", "hotel-", "assumption:"))
    for source_id in plan.source_ids
)
assert all(len(day.routes) == len(day.activities) - 1 for day in plan.days)
```

增加断开路线假服务，确认规划器减少活动数量而不编造路线。

- [ ] **Step 2: 运行测试并确认旧构造函数失败**

Run: `uv run pytest tests/test_planner.py -v`

Expected: FAIL because `Planner` still requires `amap_client`。

- [ ] **Step 3: 修改规划器，然后停止当前轮次**

移除 `AmapClient` 类型依赖。`_matching_pois()` 使用离线仓库；`_build_day()` 直接从 `OfflinePoi` 构造 `ItineraryActivity`，来源为 `offline-poi:<id>` 与景点 `source_id`。相邻景点调用 `route_service.find_route()`，用汇总结果构造 `ItineraryRoute`，`queried_at` 为带 UTC 时区的当前时间，来源为 `offline-route:<origin>:<destination>` 加路径来源。

候选排序固定为：同片区优先、通用景点次优先、名称稳定排序。某一兴趣的候选数量不足旅行天数时，追加 `is_general_highlight=True` 且尚未选用的同片区景点；路线不存在时跳过该候选，确保 `TripDay` 路线数量约束继续成立。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_planner.py tests/test_budget.py tests/test_narrator.py -v`

Commit: `refactor: generate Shanghai plans offline`

---

### Task 6: 默认 API 装配不再创建高德客户端

**Files:**
- Modify: `tests/test_api.py`
- Modify: `app/api/routes.py`

**Interfaces:**
- Consumes: 默认 SQLite 路径、`OfflineRepository`、`OfflineRouteService` 和新 `Planner` 构造函数。
- Produces: 请求结构不变的 `POST /api/plans`。

- [ ] **Step 1: 增加无 Key、禁止网络的 API 测试，然后停止当前轮次**

使用 `monkeypatch.delenv("AMAP_WEB_KEY", raising=False)`，并把 `httpx.AsyncClient.get` 替换为抛出断言的函数。直接用 `TestClient(create_app())` 提交一日问卷，断言 `200`、活动来源为 `offline-poi:` 且路线说明存在。

- [ ] **Step 2: 运行测试并确认当前默认 API 失败**

Run: `uv run pytest tests/test_api.py -v`

Expected: FAIL because default route still creates `AmapClient`。

- [ ] **Step 3: 修改默认装配，然后停止当前轮次**

`create_plan()` 默认分支创建：

```python
offline_repository = OfflineRepository(Settings().data_dir / "offline/shanghai.db")
route_service = OfflineRouteService(offline_repository)
active_planner = Planner(
    repository=preset_repository,
    offline_repository=offline_repository,
    route_service=route_service,
)
```

删除 `AmapClient` 生命周期管理，保留 `Narrator` 的关闭逻辑和统一 503 错误边界。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest tests/test_api.py -v`

Commit: `refactor: assemble offline planning API`

---

### Task 7: 完整离线端到端保证

**Files:**
- Modify: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: 默认 `create_app()`、真实 SQLite 数据库和现有 HTTP 路由。
- Produces: 外部网络被禁止时仍通过的完整流程回归测试。

- [ ] **Step 1: 将端到端测试改为真实默认规划，然后停止当前轮次**

测试必须删除高德环境变量，拦截所有目标不是 `127.0.0.1` 的 HTTP 请求，依次调用 `/api/options`、`/api/plans`、`/result` 和 `/api/export`。断言活动与路线来源为本地来源，导出 HTML 不包含 `restapi.amap.com`、`AMAP_WEB_KEY` 或 `localhost`。

- [ ] **Step 2: 运行端到端测试**

Run: `uv run pytest tests/test_end_to_end.py -v`

Expected: PASS；如果失败，只修改触发失败的单个生产文件并在修改后停止当前轮次。

- [ ] **Step 3: 提交**

Commit: `test: prove fully offline itinerary flow`

---

### Task 8: 结果页离线路线示意

**Files:**
- Create: `tests/test_frontend.py`
- Modify: `app/static/js/result.js`
- Modify: `app/static/css/app.css`

**Interfaces:**
- Consumes: `TripDay.activities` 坐标与 `TripDay.routes` 实用级摘要。
- Produces: `#route-diagram` 简化 SVG/HTML 示意和“离线路线示意”措辞。

- [ ] **Step 1: 创建前端契约测试，然后停止当前轮次**

测试读取静态文件并断言 `result.js` 包含 `renderRouteDiagram` 和“离线路线示意”，不再包含“高德 Web 服务”；CSS 包含固定 `aspect-ratio`、`.route-diagram` 和手机断点。

- [ ] **Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/test_frontend.py -v`

- [ ] **Step 3: 修改结果 JavaScript，然后停止当前轮次**

增加 `renderRouteDiagram(day)`：以当天经纬度的最小最大值归一化为 0–100 坐标，保留 8 单位内边距；单一景点居中；使用 DOM 创建 SVG `polyline`、圆点和按访问顺序编号的文本。所有动态文本继续使用 `textContent` 或 `escapeHtml`，不得拼入未经转义的来源内容。

路线文字显示方式、预计时间、近似距离和 `instructions.join("；")`，底部固定显示“离线路线示意 · 时间与距离为实用级估算”。

- [ ] **Step 4: 修改 CSS，然后停止当前轮次**

`.route-diagram` 使用稳定 `aspect-ratio: 4 / 3`、1px 边框、非单色纸张背景；SVG 宽高 100%，路线使用玉绿色，序号使用信号红。手机端保持最小高度，不允许路线示意改变侧栏宽度或产生横向滚动。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_frontend.py tests/test_index_page.py tests/test_result_page.py -v`

Commit: `feat: show offline route diagrams`

---

### Task 9: 导出与说明切换为离线来源

**Files:**
- Modify: `app/templates/export.html`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: 现有 `TripPlan` 和 SQLite 数据更新时间。
- Produces: 不暗示实时地图的独立 HTML 与离线安装说明。

- [ ] **Step 1: 修改导出模板，然后停止当前轮次**

路线标题使用“离线路线参考”，页脚说明“景点和路线来自项目内置数据库，预计时间与距离不代表实时导航”。不得加载外部 CSS、脚本、字体或地图资源。

- [ ] **Step 2: 运行导出测试**

Run: `uv run pytest tests/test_exporter.py -v`

- [ ] **Step 3: 修改 `.env.example`，然后停止当前轮次**

移除必需的 `AMAP_WEB_KEY` 和 `AMAP_JS_KEY` 示例，只保留可选 Ollama 配置。真实本地 `.env` 继续被忽略，不纳入提交。

- [ ] **Step 4: 修改 README，然后停止当前轮次**

README 说明无需地图 Key、数据库位置、60 个精选景点、实用级路线限制、OpenStreetMap ODbL 归属、数据库重建命令和数据维护规则。删除“配置高德”作为启动前提，保留 Ollama 可选降级说明。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest tests/test_exporter.py tests/test_end_to_end.py -v`

Commit: `docs: document fully offline operation`

---

### Task 10: 浏览器与容量验收

**Files:**
- Modify only if a verified defect requires it; obey one-file stop checkpoints.

**Interfaces:**
- Consumes: 完整离线应用。
- Produces: 桌面与手机验收证据。

- [ ] **Step 1: 全量自动化验证**

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python scripts/check_sizes.py
git diff --check
```

Expected: 全部退出码为 0；Git 内容小于 500MB；本地环境小于 1.5GB。

- [ ] **Step 2: 无网络配置启动**

在临时环境中移除高德变量后运行：

```bash
env -u AMAP_WEB_KEY -u AMAP_JS_KEY uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 3: 浏览器验收**

检查 1440×900 与 390×844：完成七步问卷、生成至少两日行程、切换日期、查看路线示意、导出 HTML。确认无控制台错误、无横向溢出、长景点名不遮挡、路线编号和文字对应。

- [ ] **Step 4: 敏感信息与外部依赖检查**

Run: `git ls-files | rg '(^|/)\.env$'`

Expected: 无输出。Run: `git ls-files data/offline/shanghai.db`，Expected: 只输出受控数据库路径。Run: `task_amap_key=$(sed -n 's/^AMAP_WEB_KEY=//p' .env); test -z "$task_amap_key" || ! git grep -F "$task_amap_key"`，Expected: 退出码为 0 且不显示 Key。再运行 `rg -n 'restapi\.amap\.com|高德 Web 服务' app README.md`，默认运行路径和用户说明不得包含高德依赖。

- [ ] **Step 5: 提交最终修正并推送开发分支**

只有实际修正时才创建提交；全部验证通过后推送 `codex/tourguide-mvp`，不自动合并 `main`。
