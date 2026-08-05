"""结果页离线路线示意图的静态契约测试。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_JS_PATH = PROJECT_ROOT / "app/static/js/result.js"
APP_CSS_PATH = PROJECT_ROOT / "app/static/css/app.css"


def test_result_js_exposes_offline_route_diagram_contract() -> None:
    source = RESULT_JS_PATH.read_text(encoding="utf-8")

    assert "renderRouteDiagram" in source
    assert "离线路线示意" in source
    assert "高德 Web 服务" not in source


def test_result_js_builds_diagram_with_dom_svg_and_safe_text() -> None:
    source = RESULT_JS_PATH.read_text(encoding="utf-8")

    assert 'createElementNS("http://www.w3.org/2000/svg"' in source
    assert ".textContent" in source
    assert 'instructions.join("；")' in source


def test_result_css_styles_route_diagram_with_fixed_ratio_and_paper() -> None:
    stylesheet = APP_CSS_PATH.read_text(encoding="utf-8")

    assert ".route-diagram" in stylesheet
    assert "aspect-ratio: 4 / 3" in stylesheet
    assert "linear-gradient" in stylesheet


def test_result_css_keeps_route_diagram_stable_on_mobile() -> None:
    stylesheet = APP_CSS_PATH.read_text(encoding="utf-8")
    mobile_block = stylesheet.split("@media (max-width: 760px)")[1].split("@media")[0]

    assert ".route-diagram" in mobile_block
    assert "min-height" in mobile_block
