from urllib.parse import unquote

from app.services.exporter import HtmlExporter


def test_exporter_creates_self_contained_html(sample_plan) -> None:
    html = HtmlExporter().render(sample_plan)

    assert "<!doctype html>" in html.lower()
    assert "预算明细" in html
    assert "1960.20" in html
    assert "上海博物馆" in html
    assert "参考价格" in html
    assert "离线路线参考" in html
    assert "景点和路线来自项目内置数据库，预计时间与距离不代表实时导航。" in html
    assert "localhost" not in html
    assert "AMAP_WEB_KEY" not in html


def test_export_endpoint_downloads_named_html(client, sample_plan) -> None:
    response = client.post("/api/export", json=sample_plan.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "tourGuide-上海-20261002.html" in unquote(response.headers["content-disposition"])
    assert "上海博物馆" in response.text
