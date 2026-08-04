def test_result_page_renders_budget_and_sources(client, sample_plan) -> None:
    response = client.post("/result", json=sample_plan.model_dump(mode="json"))

    assert response.status_code == 200
    assert "预算明细" in response.text
    assert "参考价格" in response.text
    assert "数据更新时间" in response.text
    assert 'id="plan-data"' in response.text


def test_result_page_contains_itinerary_controls(client, sample_plan) -> None:
    response = client.post("/result", json=sample_plan.model_dump(mode="json"))

    assert 'id="day-tabs"' in response.text
    assert 'id="day-timeline"' in response.text
    assert 'id="route-summary"' in response.text
    assert 'id="export-plan"' in response.text
    assert "/static/js/result.js" in response.text


def test_result_shell_supports_browser_session_plan(client) -> None:
    response = client.get("/result")

    assert response.status_code == 200
    assert 'lang="zh-CN"' in response.text
    assert "未找到行程" in response.text
