# tourGuide

tourGuide 是一个本地运行的上海旅游规划网页。它通过七步固定问答收集出发城市、人数、日期、预算、兴趣和交通偏好，再组合可追溯参考价格、高德地点与路线，生成可查看和导出的每日行程。

项目用于实习展示，第一版强调结构清楚、数据有来源和离线降级，不提供预订、支付、账号或云同步。

## 功能范围

- 目的地固定为上海。
- 出发地支持合肥、芜湖、蚌埠、淮南、阜阳、安庆、黄山、马鞍山、滁州和南京。
- 住宿、大交通和预算均由 Python 使用整数“分”计算。
- 高德 Web 服务负责 POI、上海市内路线和天气数据适配。
- 携程公开页面的人工核验价格保存在本地 JSON，并记录来源 URL 和日期。
- 本地 Ollama 模型只整理已生成的结构化事实；模型不可用时自动使用固定模板。
- 结果可导出为不依赖本地服务器的独立 HTML。

本项目不抓取携程网页，不生成实时票价，不执行任何购买操作，也不把问卷或行程上传到云端。

## 项目结构

```text
app/
  api/             页面与 JSON API
  repositories/    本地预设和参考价格读取
  schemas/         问卷、预算和行程模型
  services/        高德、交通、住宿、预算、规划、文字和导出服务
  static/          本地 CSS、JavaScript 和上海图片
  templates/       问卷、结果和导出模板
data/
  presets/         城市、兴趣和上海候选 POI
  reference/       带来源的参考价格
scripts/           容量检查脚本
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

## 配置高德

复制环境变量示例：

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
AMAP_WEB_KEY=你的高德Web服务Key
AMAP_JS_KEY=
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:0.5b
```

`AMAP_WEB_KEY` 用于后端地点和路线请求。`AMAP_JS_KEY` 仅为后续交互地图预留，当前文本路线不需要填写。真实 Key 只能放在 `.env`，不得写入代码、提交记录、截图或导出文件。

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

## 启动网页

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

首页完成七步问答后生成上海行程。结果页可切换日期，并通过“导出 HTML”保存独立文件。

## 测试与检查

运行全部验证：

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python scripts/check_sizes.py
```

测试使用固定高德响应和本地假服务，不消耗真实高德配额，也不要求 Ollama 在线。

## 数据更新规则

参考价格位于 `data/reference/prices.json`。维护时必须：

1. 通过公开页面人工核验，不编写抓取程序。
2. 金额统一换算为整数分。
3. 保存唯一 `id`、来源 URL、查看日期和适用日期。
4. 最低价不得高于最高价，适用结束日期不得早于开始日期。
5. 新增交通段或收费景点时同步补充来源 ID 和自动化测试。

上海候选地点位于 `data/presets/shanghai_pois.json`。地点名称会在生成时交给高德核验；无法获取可靠地点或相邻路线时，不会用模型补充替代事实。

界面横幅使用 Wikimedia Commons 的 CC0 图片 `Pudong Skyline from The Bund 20260417`，原始来源和许可证记录在 `app/templates/index.html` 的代码注释中。

## 公开仓库协作

仓库公开意味着任何人都可以查看和 Fork，但其他人不能直接修改你的仓库。外部修改应通过 Pull Request 提交，由仓库维护者审查同意后再合并。
