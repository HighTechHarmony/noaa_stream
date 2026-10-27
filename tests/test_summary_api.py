import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from scripts.summary_api import (
    SECTIONS,
    InvalidSummary,
    Settings,
    _normalize_and_validate,
    create_app,
    load_settings,
)


def make_settings(directory, **overrides):
    values = {
        "config_path": directory / "config.toml",
        "forecast_dir": directory,
        "ollama_url": "http://ollama.test:11434",
        "ollama_model": "test-model",
        "connect_timeout_seconds": 0.5,
        "read_timeout_seconds": 0.5,
        "generation_deadline_seconds": 1.0,
        "host": "127.0.0.1",
        "port": 8765,
        "max_concurrent_summaries": 2,
        "queue_timeout_seconds": 0.2,
        "source_max_bytes": 1024,
        "source_settle_seconds": 0,
    }
    values.update(overrides)
    return Settings(**values)


def ollama_response(sentences):
    content = json.dumps({"sentences": sentences})
    return httpx.Response(200, json={"message": {"content": content}})


def write_forecasts(directory):
    for section in SECTIONS:
        (directory / f"{section}.txt").write_text(
            f"{section} forecast: rain likely this afternoon.", encoding="utf-8"
        )


def test_each_forecast_section_is_available_and_within_limits(tmp_path):
    write_forecasts(tmp_path)
    requests = []

    async def handler(request):
        requests.append(json.loads(request.content))
        return ollama_response(["Rain is likely this afternoon."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        for section in SECTIONS:
            response = client.get(f"/api/v1/forecasts/{section}/message_summary")
            assert response.status_code == 200
            body = response.json()
            assert body["section"] == section
            assert body["sentences"] == ["Rain is likely this afternoon."]
            assert body["summary"] == "Rain is likely this afternoon."
            assert body["character_count"] == sum(map(len, body["sentences"]))
            assert body["sentence_count"] == 1
            assert body["cached"] is False
    assert len(requests) == 4
    assert all(request["model"] == "test-model" for request in requests)


def test_raw_forecast_endpoints_return_exact_plain_text_without_ollama(tmp_path):
    write_forecasts(tmp_path)

    async def handler(request):
        pytest.fail("raw forecast endpoint must not call Ollama")

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        for section in SECTIONS:
            original = f"{section} forecast.\r\nSecond line.  \n".encode()
            (tmp_path / f"{section}.txt").write_bytes(original)
            response = client.get(f"/api/v1/forecasts/{section}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            assert response.content == original


def test_cache_reuses_summary_until_source_changes(tmp_path):
    write_forecasts(tmp_path)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return ollama_response(["Rain is likely."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        first = client.get("/api/v1/forecasts/synopsis/message_summary").json()
        second = client.get("/api/v1/forecasts/synopsis/message_summary").json()
        assert first["cached"] is False
        assert second["cached"] is True
        (tmp_path / "synopsis.txt").write_text("Updated forecast.", encoding="utf-8")
        third = client.get("/api/v1/forecasts/synopsis/message_summary").json()
        assert third["cached"] is False
    assert calls == 2


def test_unknown_section_and_missing_source_return_not_found(tmp_path):
    app = create_app(make_settings(tmp_path), httpx.MockTransport(lambda request: ollama_response(["Fine."])))
    with TestClient(app) as client:
        assert client.get("/api/v1/forecasts/unknown").status_code == 404
        assert client.get("/api/v1/forecasts/unknown/message_summary").status_code == 404
        assert client.get("/api/v1/forecasts/synopsis/message_summary").status_code == 404


def test_empty_and_invalid_encoding_sources_are_rejected(tmp_path):
    source = tmp_path / "synopsis.txt"
    source.write_bytes(b" \n")
    app = create_app(make_settings(tmp_path), httpx.MockTransport(lambda request: ollama_response(["Fine."])))
    with TestClient(app) as client:
        assert client.get("/api/v1/forecasts/synopsis/message_summary").json()["detail"]["code"] == "source_empty"
        source.write_bytes(b"\xff")
        assert client.get("/api/v1/forecasts/synopsis/message_summary").json()["detail"]["code"] == "source_invalid_encoding"


def test_summary_validation_accepts_exactly_133_and_rejects_134_chars():
    sentences, count = _normalize_and_validate(json.dumps({"sentences": ["A" * 132 + "."]}))
    assert len(sentences[0]) == 133
    assert count == 1
    with pytest.raises(InvalidSummary, match="133"):
        _normalize_and_validate(json.dumps({"sentences": ["A" * 133 + "."]}))


def test_four_sentences_can_each_use_the_full_133_character_limit():
    sentence = "A" * 132 + "."
    sentences, count = _normalize_and_validate(json.dumps({"sentences": [sentence] * 4}))
    assert sentences == [sentence] * 4
    assert sum(map(len, sentences)) == 532
    assert count == 4


def test_summary_validation_splits_sentences_grouped_in_one_array_item():
    sentences, count = _normalize_and_validate(
        json.dumps({"sentences": ["Rain is likely today. Winds increase tonight."]})
    )
    assert sentences == ["Rain is likely today.", "Winds increase tonight."]
    assert count == 2


def test_summary_validation_keeps_sentences_even_when_joined_text_exceeds_133_chars():
    first = "A" * 69 + "."
    second = "B" * 61 + "."
    third = "C."
    sentences, count = _normalize_and_validate(
        json.dumps({"sentences": [f"{first} {second} {third}"]})
    )
    assert sentences == [first, second, third]
    assert len(" ".join(sentences)) > 133
    assert count == 3


@pytest.mark.parametrize(
    "content",
    [
        json.dumps({"sentences": ["One.", "Two.", "Three.", "Four.", "Five."]}),
        json.dumps({"sentences": ["One. Two. Three. Four. Five."]}),
        json.dumps({"sentences": ["- A list item."]}),
        json.dumps({"sentences": ["Non-ASCII: café."]}),
        "not json",
        json.dumps({"sentences": ["No terminal punctuation"]}),
    ],
)
def test_invalid_summaries_are_rejected(content):
    with pytest.raises(InvalidSummary):
        _normalize_and_validate(content)


def test_invalid_model_output_gets_one_correction_attempt(tmp_path):
    write_forecasts(tmp_path)
    calls = []

    async def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return ollama_response(["X" * 134 + "."])
        return ollama_response(["A safer forecast."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        result = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert result.status_code == 200
    assert result.json()["summary"] == "A safer forecast."
    assert len(calls) == 2
    assert "failed validation" in calls[1]["messages"][0]["content"]
    assert "Previous draft text" in calls[1]["messages"][0]["content"]


def test_non_ascii_model_output_gets_corrected_before_returning_summary(tmp_path):
    write_forecasts(tmp_path)
    calls = []

    async def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return ollama_response(["Rain is likely near Montréal."])
        return ollama_response(["Rain is likely near Montreal."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    body = response.json()
    assert body["sentences"] == ["Rain is likely near Montreal."]
    assert body["sentences"][0].isascii()
    assert len(body["sentences"][0]) <= 133
    assert body["sentences"][0].endswith((".", "!", "?"))
    assert body["sentence_count"] <= 4
    assert len(calls) == 2
    assert "printable ASCII characters only" in calls[1]["messages"][0]["content"]


def test_repeated_invalid_output_is_not_cached(tmp_path):
    write_forecasts(tmp_path)

    async def handler(request):
        return ollama_response(["X" * 134 + "."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_ollama_response"


@pytest.mark.parametrize(
    ("upstream_status", "status", "code"),
    [(500, 503, "ollama_unavailable"), (404, 502, "ollama_rejected")],
)
def test_ollama_http_errors_are_classified(upstream_status, status, code, tmp_path):
    write_forecasts(tmp_path)

    async def handler(request):
        return httpx.Response(upstream_status, json={"error": "upstream error"})

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (httpx.ConnectError("offline"), 503, "ollama_unavailable"),
        (httpx.ReadTimeout("slow"), 504, "ollama_timeout"),
    ],
)
def test_ollama_failures_have_bounded_error_responses(tmp_path, error, status, code):
    write_forecasts(tmp_path)

    async def handler(request):
        raise error

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_slow_ollama_response_within_configured_deadline_is_accepted(tmp_path):
    write_forecasts(tmp_path)

    async def handler(request):
        await asyncio.sleep(0.05)
        return ollama_response(["Rain is likely."])

    settings = make_settings(tmp_path, read_timeout_seconds=0.2, generation_deadline_seconds=0.2)
    app = create_app(settings, httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert response.status_code == 200


def test_healthcheck_never_calls_ollama(tmp_path):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline")

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
    assert calls == 0


def test_changed_source_during_generation_is_retried_before_caching(tmp_path):
    write_forecasts(tmp_path)
    source_path = tmp_path / "synopsis.txt"
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            source_path.write_text("New forecast after first request.", encoding="utf-8")
            return ollama_response(["Old forecast."])
        return ollama_response(["New forecast."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert response.status_code == 200
    assert response.json()["summary"] == "New forecast."
    assert calls == 2


def test_settings_resolve_forecast_dir_relative_to_config(tmp_path):
    forecast_dir = tmp_path / "forecasts"
    forecast_dir.mkdir()
    config_path = tmp_path / "service.toml"
    config_path.write_text(
        '[ollama]\nurl = "http://localhost:11434"\nmodel = "test"\n'
        '[paths]\nforecast_dir = "forecasts"\n',
        encoding="utf-8",
    )
    assert load_settings(config_path).forecast_dir == forecast_dir


def test_settings_reject_invalid_ollama_url(tmp_path):
    config_path = tmp_path / "service.toml"
    config_path.write_text(
        '[ollama]\nurl = "file:///tmp/model"\nmodel = "test"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        load_settings(config_path)


def test_parallel_requests_for_same_source_are_deduplicated(tmp_path):
    write_forecasts(tmp_path)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return ollama_response(["Rain is likely."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    lambda _: client.get("/api/v1/forecasts/synopsis/message_summary"), range(2)
                )
            )
    assert all(response.status_code == 200 for response in responses)
    assert calls == 1