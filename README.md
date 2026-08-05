# tourGuide

tourGuide 是一个本地运行的上海旅游规划网页。它通过七步固定问答收集出发城市、人数、日期、预算、兴趣和交通偏好，再组合内置数据库中的精选景点、路线和可追溯参考价格，生成可查看和导出的每日行程。

项目用于实习展示，第一版强调结构清楚、数据有来源和离线降级，不提供预订、支付、账号或云同步。

本版已由在线地图方案改为本地化版本[^version]，运行时不请求任何地图服务。

## 功能范围

- 目的地固定为上海。
- 出发地支持合肥、芜湖、蚌埠、淮南、阜阳、安庆、黄山、马鞍山、滁州和南京。
- 住宿、大交通和预算均由 Python 使用整数“分”计算。
- 内置 SQLite 数据库提供 60 个精选景点、实用级路线连接和来源标识，无需申请或配置地图 API Key。
- 携程公开页面的人工核验价格保存在本地 JSON，并记录来源 URL 和日期。
- 本地 Ollama 模型只整理已生成的结构化事实；模型不可用时自动使用固定模板。
- 路线时间和距离为人工整理的实用级估算，不代表实时导航。
- 结果可导出为不依赖本地服务器的独立 HTML。

本项目不抓取携程网页，不生成实时票价，不执行任何购买操作，也不把问卷或行程上传到云端。

## 技术栈

- Python 3.12 与标准库 `sqlite3`、`heapq`；
- FastAPI、Pydantic、Jinja2；
- SQLite 离线数据库与可审查的 JSON 种子数据；
- 原生 JavaScript 与 CSS，不依赖前端框架或地图 SDK；
- `uv` 管理依赖，pytest 与 Ruff 负责测试和检查。

## 项目结构

```text
app/
  api/             页面与 JSON API
  repositories/    本地预设、参考价格和离线数据库读取
  schemas/         问卷、预算、行程和离线数据模型
  services/        离线路线、交通、住宿、预算、规划、文字和导出服务
  static/          本地 CSS、JavaScript 和上海图片
  templates/       问卷、结果和导出模板
data/
  offline/         上海离线数据库及其种子数据
  presets/         城市、兴趣和上海候选 POI
  reference/       带来源的参考价格
scripts/           数据库构建和容量检查脚本
tests/             单元、接口和端到端测试
```

## 容量限制

- Git 跟踪文件硬性上限为 500MB，正常目标不超过 100MB。
- 当前项目 `.venv` 与默认 Ollama 模型合计不得超过 1.5GB。
- `.venv`、模型、密钥、缓存、日志和用户导出文件均不会提交到 GitHub。

检查容量：

```bash
uv run python scripts/check_sizes.py
```

CI 只执行 Git 文件检查，不要求安装 Ollama：

```bash
uv run python scripts/check_sizes.py --git-only
```

## 安装 Python 环境

项目固定使用 Python 3.12 和根目录 `.venv`，不要复用其他项目的环境。

```bash
command -v uv || brew install uv
uv python install 3.12
uv sync --locked --dev
```

确认解释器：

```bash
uv run python --version
```

应输出 `Python 3.12.x`。VS Code 已通过 `.vscode/settings.json` 使用：

```text
${workspaceFolder}/.venv/bin/python
```

如果 VS Code 没有自动切换，可执行“Python: Select Interpreter”，再选择上述路径。

## 可选配置：本地模型（Ollama）

Ollama 是可选降级方案。默认行程生成不依赖任何外部服务，也不要求 Ollama 在线；只有文字整理功能会尝试调用本地模型，模型不可用时自动改用固定模板。

如需启用，先复制环境变量示例：

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:0.5b
```

`OLLAMA_BASE_URL` 指向本地 Ollama 服务，`OLLAMA_MODEL` 指定文字整理使用的小模型。`.env` 已被 Git 忽略，只保存在本地，不纳入提交。

## 安装本地模型

macOS：

```bash
brew install ollama
ollama serve
```

另开一个终端下载默认小模型：

```bash
ollama pull qwen2.5:0.5b
```

项目不使用 DeepSeek 或其他云端模型 API。Ollama 未启动或模型响应失败时，行程仍会生成，文字部分自动改用固定模板。

## 离线数据

行程生成完全使用项目内置数据库，不需要地图 API Key，也不需要外部网络。网页运行期间数据库以只读方式打开，不会修改或上传用户数据。

- 数据库位置：`data/offline/shanghai.db`，由 `scripts/build_offline_db.py` 从种子数据确定性生成。
- 种子数据：`data/offline/shanghai_seed.json`，包含 60 个精选景点、6 类旅行兴趣、105 条实用级路线连接，以及带许可证和核验日期的来源记录。
- 路线限制：路线时间和距离是人工整理的实用级估算，只覆盖同片区和相邻片区的主要连接；缺少直接连接时允许经由中间景点计算最短路径。它们用于行程规划参考，不代表实时路况、地铁到站或导航指令。
- 数据归属：景点坐标采用 OpenStreetMap 贡献者数据，依据 ODbL 1.0 再分发；景点名称、开放提示和票价优先采用上海市文旅部门和场馆官方网站，地铁连接采用上海地铁公开信息。归属同时保留在 README、数据库 `sources` 表和导出结果的来源说明中。

### 重建数据库

修改种子数据后，用确定性命令重建数据库：

```bash
uv run python scripts/build_offline_db.py \
  --seed data/offline/shanghai_seed.json \
  --output data/offline/shanghai.db
```

构建按固定顺序导入全部表与约束，成功后原子替换目标文件，重复构建结果一致。重建后运行数据库测试：

```bash
uv run pytest tests/test_offline_builder.py tests/test_offline_repository.py -v
```

### 数据维护规则

- 新增或修改景点、路线和来源前，先在 `data/offline/shanghai_seed.json` 中人工核验，不编写抓取程序。
- 坐标只能使用允许公开再分发的 OpenStreetMap 数据，不复制第三方地图 API 的响应数据或坐标。
- 景点名称、开放提示和门票优先采用上海市文旅部门、场馆或景点官方网站，并保存来源 URL 和核验日期。
- 地铁连接使用上海地铁公开信息，不含实时到站数据；路线时间和距离为人工估算的实用级近似值，并在 `verified_at` 记录核验日期。
- 金额统一换算为整数分，最低价不得高于最高价，适用结束日期不得早于开始日期。
- 修改后必须重建数据库并运行数据库、路线和规划测试，确认外键、唯一约束和数值检查全部通过。

## 启动网页

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

无需配置任何地图 Key，断网时仍可完成从问卷到导出 HTML 的完整流程。首页完成七步问答后生成上海行程，结果页可切换日期，并通过“导出 HTML”保存独立文件。

## 常用接口

| 接口 | 说明 |
| --- | --- |
| `GET /` | 七步问卷首页 |
| `GET /result` | 结果页（无计划时为空壳） |
| `POST /result` | 提交完整计划并渲染结果页 |
| `GET /api/options` | 支持的城市、兴趣与偏好选项 |
| `POST /api/plans` | 提交问卷并生成上海行程 |
| `POST /api/export` | 导出完全自包含的独立 HTML |
| `GET /health` | 健康检查 |

接口请求与响应均使用 JSON；`/api/plans` 的请求结构与上一版本保持一致。

## 测试与检查

运行全部验证：

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python scripts/check_sizes.py
```

测试使用内置数据库和本地假服务，并拦截外部网络请求，不消耗任何 API 配额，也不要求 Ollama 在线。

## 常见问题

- 提示“离线数据库缺失或版本不兼容”怎么办？
  运行数据库重建命令（见“重建数据库”一节），确认 `data/offline/shanghai.db` 存在且版本为 1。
- 不配置高德 Key 能用吗？
  能。默认规划完全使用内置 SQLite 数据，不读取任何地图 Key，断网也可运行。
- 结果页的文字没有润色？
  Ollama 是可选服务，未安装或未启动时自动使用固定模板，不影响行程与预算。
- 想新增或调整景点？
  编辑 `data/offline/shanghai_seed.json` 后重建数据库，并运行数据库、路线与规划测试。
- 浏览器打开 8000 端口失败？
  确认先执行“启动网页”中的命令，且端口未被其他进程占用。

## 数据更新规则

参考价格位于 `data/reference/prices.json`。维护时必须：

1. 通过公开页面人工核验，不编写抓取程序。
2. 金额统一换算为整数分。
3. 保存唯一 `id`、来源 URL、查看日期和适用日期。
4. 最低价不得高于最高价，适用结束日期不得早于开始日期。
5. 新增交通段或收费景点时同步补充来源 ID 和自动化测试。

上海景点与路线位于 `data/offline/shanghai_seed.json`（构建后为 `data/offline/shanghai.db`），维护方式见“离线数据”一节。规划器只使用数据库中有来源的事实；缺少可靠地点或相邻路线时跳过对应候选，不会用模型补充替代事实。

界面横幅使用 Wikimedia Commons 的 CC0 图片 `Pudong Skyline from The Bund 20260417`，原始来源和许可证记录在 `app/templates/index.html` 的代码注释中。

## 版本说明

- 2026-08-05 · 本地化版本：用内置 SQLite 数据库替换运行时高德调用，新增 60 个精选景点与 105 条实用级路线，结果页改为离线路线示意，导出与文档同步更新为离线说明。

## 公开仓库协作

仓库公开意味着任何人都可以查看和 Fork，但其他人不能直接修改你的仓库。外部修改应通过 Pull Request 提交，由仓库维护者审查同意后再合并。

[^version]: 改为本地化版本
