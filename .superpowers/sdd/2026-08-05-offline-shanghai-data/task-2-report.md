# Task 2 报告

## 状态

DONE

## 改动

- 新增 `data/offline/shanghai_seed.json`，包含固定 UTC `generated_at`、5 个来源、6 个兴趣、简报指定的恰好 60 个上海景点、景点兴趣关系和 105 条路线边。
- 新增 `scripts/build_offline_db.py`，以事务创建带外键、唯一约束和数值 CHECK 的 SQLite schema；按稳定 ID 排序导入，并通过临时文件和 `Path.replace()` 原子替换输出。
- 生成 `data/offline/shanghai.db`（schema version `1`）。
- 新增 `tests/test_offline_builder.py`，覆盖完整性、外键检查和重复构建确定性。

## RED/GREEN 测试

- RED（简报要求的实现前检查）：构建模块尚不存在时，`uv run pytest tests/test_offline_builder.py -v` 预期为 `ModuleNotFoundError`；现有提交中已完成实现，无法在本轮重放该历史状态。
- GREEN：`uv run pytest tests/test_offline_builder.py -v`：2 passed。

## 命令与结果

- `uv run python scripts/build_offline_db.py --seed data/offline/shanghai_seed.json --output data/offline/shanghai.db`：成功生成数据库。
- `uv run ruff check scripts/build_offline_db.py tests/test_offline_builder.py`：`All checks passed!`。
- `uv run pytest -q`：57 passed。
- 独立重建临时数据库并与提交的 `data/offline/shanghai.db` 比较：字节一致；数据库查询确认 60 个景点、6 个兴趣、105 条路线边，`foreign_key_check` 为空。

## 自检

- 所有景点名称与简报清单逐项匹配；每个景点关联 1–3 个兴趣，坐标、区域、片区、时长、费用、开放提示、来源和核验日期均存在。
- 来源包含 OpenStreetMap ODbL 归属、上海市文化和旅游局、上海地铁和场馆官方网站；路线边端点均引用现有景点。
- `generated_at` 直接来自种子元数据，构建过程不读取系统当前时间；重复构建 `iterdump()` 内容相同。
- 失败时临时文件清理并保留既有目标文件；未读取或修改 `.env`。

## Concerns

- 景点开放时间、票价和路线时长是按简报要求保存的人工核验提示/估算，不是实时导航或实时运营数据；使用时应以场馆和交通官方公告为准。
