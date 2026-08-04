from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
from app.schemas.trip import TripPlan


class HtmlExporter:
    """将完整行程渲染为无需本地服务的独立 HTML。"""

    def __init__(self, template_dir: Path | None = None) -> None:
        directory = template_dir or Settings().project_root / "app" / "templates"
        self._environment = Environment(
            loader=FileSystemLoader(directory),
            autoescape=select_autoescape(("html", "xml")),
        )

    def render(self, plan: TripPlan) -> str:
        """返回已内联样式的 UTF-8 HTML 文本。"""
        template = self._environment.get_template("export.html")
        return template.render(plan=plan)
