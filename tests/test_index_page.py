def test_index_contains_questionnaire_shell(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="questionnaire"' in response.text
    assert 'id="trip-summary"' in response.text
    assert 'lang="zh-CN"' in response.text
    assert 'id="question-progress"' in response.text
    assert 'aria-live="polite"' in response.text


def test_index_loads_local_styles_script_and_shanghai_image(client) -> None:
    response = client.get("/")

    assert "/static/css/app.css" in response.text
    assert "/static/js/questionnaire.js" in response.text
    assert "/static/images/shanghai-riverside.webp" in response.text
    assert 'src="https://' not in response.text
    assert 'href="https://' not in response.text


def test_index_contains_all_seven_question_steps(client) -> None:
    response = client.get("/")

    for step in range(1, 8):
        assert f'data-step="{step}"' in response.text
    assert 'name="origin_city"' in response.text
    assert 'name="budget_includes_intercity"' in response.text
    assert 'name="intercity_preference"' in response.text
