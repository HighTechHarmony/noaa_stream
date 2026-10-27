import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
        "ollama_num_ctx": 8192,
        "diagnostic_log_path": directory / "logs" / "summary_api.jsonl",
        "diagnostic_log_enabled": True,
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

    app = create_app(make_settings(tmp_path, ollama_num_ctx=4096), httpx.MockTransport(handler))
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
    assert all(request["options"]["num_ctx"] == 4096 for request in requests)


def test_ollama_prompt_and_unmodified_response_are_logged(tmp_path):
    write_forecasts(tmp_path)
    requests = []
    raw_response = (
        b'{ "message" : { "content" : "{\\"sentences\\":[\\"Rain is likely.\\"]}" }, "done": true }'
    )

    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=raw_response,
            headers={"content-type": "application/json"},
        )

    settings = make_settings(tmp_path)
    app = create_app(settings, httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    records = [
        json.loads(line)
        for line in settings.diagnostic_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["section"] == "synopsis"
    assert records[0]["model"] == "test-model"
    assert records[0]["prompt"] == requests[0]["messages"][0]["content"]
    assert records[0]["response_status"] == 200
    assert records[0]["response_body"] == raw_response.decode("utf-8")
    assert records[0]["request_error"] is None


def test_diagnostic_log_write_failure_does_not_fail_summary_request(tmp_path, caplog):
    write_forecasts(tmp_path)

    async def handler(request):
        return ollama_response(["Rain is likely."])

    settings = make_settings(tmp_path, diagnostic_log_path=tmp_path)
    app = create_app(settings, httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    assert response.json()["sentences"] == ["Rain is likely."]
    assert "Unable to write summary diagnostic log" in caplog.text


def test_diagnostic_logging_can_be_disabled(tmp_path):
    write_forecasts(tmp_path)

    async def handler(request):
        return ollama_response(["Rain is likely."])

    settings = make_settings(tmp_path, diagnostic_log_enabled=False)
    app = create_app(settings, httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    assert response.json()["sentences"] == ["Rain is likely."]
    assert not settings.diagnostic_log_path.exists()


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


def test_summary_normalization_preserves_133_and_truncates_longer_sentences():
    sentences, count = _normalize_and_validate(json.dumps({"sentences": ["A" * 132 + "."]}))
    assert len(sentences[0]) == 133
    assert count == 1
    sentences, count = _normalize_and_validate(json.dumps({"sentences": ["A" * 133 + "."]}))
    assert sentences == ["A" * 130 + "..."]
    assert len(sentences[0]) == 133
    assert count == 1


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
        "not json",
        json.dumps({"summary": "Missing sentences array"}),
        json.dumps({"sentences": ["", None]}),
    ],
)
def test_summary_normalization_rejects_only_unusable_structure(content):
    with pytest.raises(InvalidSummary):
        _normalize_and_validate(content)


def test_summary_normalization_sanitizes_unicode_and_controls():
    sentences, count = _normalize_and_validate(
        json.dumps({"sentences": ["Café — Montréal 🌧\nRain later"]})
    )
    assert sentences == ["Cafe - Montreal Rain later"]
    assert count == 1
    assert sentences[0].isascii()
    assert all(32 <= ord(character) <= 126 for character in sentences[0])


def test_summary_normalization_does_not_require_or_change_terminal_punctuation():
    sentences, count = _normalize_and_validate(
        json.dumps({"sentences": ["Rain likely", "Windy later!"]})
    )
    assert sentences == ["Rain likely", "Windy later!"]
    assert count == 2


def test_summary_normalization_keeps_first_four_sentences():
    sentences, count = _normalize_and_validate(
        json.dumps({"sentences": ["One. two. three. four. five."]})
    )
    assert sentences == ["One.", "two.", "three.", "four."]
    assert count == 4


def test_noncompliant_model_output_is_sanitized_without_retry(tmp_path):
    write_forecasts(tmp_path)
    calls = []

    async def handler(request):
        calls.append(json.loads(request.content))
        return ollama_response(
            ["Rain showers may continue near Montréal through the afternoon. " + "W" * 140]
        )

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        result = client.get("/api/v1/forecasts/synopsis/message_summary")
    assert result.status_code == 200
    body = result.json()
    assert len(body["sentences"]) == 2
    assert body["sentences"][0] == "Rain showers may continue near Montreal through the afternoon."
    assert len(body["sentences"][1]) == 133
    assert body["sentences"][1].endswith("...")
    assert all(sentence.isascii() for sentence in body["sentences"])
    assert len(calls) == 1


def test_non_ascii_model_output_is_transliterated_before_returning_summary(tmp_path):
    write_forecasts(tmp_path)
    calls = []

    async def handler(request):
        calls.append(json.loads(request.content))
        return ollama_response(["Rain is likely near Montréal."])

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
    assert len(calls) == 1


def test_more_than_four_sentences_are_limited_without_retry(tmp_path):
    write_forecasts(tmp_path)
    calls = []

    async def handler(request):
        calls.append(json.loads(request.content))
        return ollama_response(["One. Two. Three. Four. Five."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    body = response.json()
    assert body["sentences"] == ["One.", "Two.", "Three.", "Four."]
    assert body["sentence_count"] == 4
    assert len(calls) == 1


def test_persistent_excess_sentences_are_limited_to_first_four_in_one_call(tmp_path):
    write_forecasts(tmp_path)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return ollama_response(["One.", "Two.", "Three.", "Four.", "Five."])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    assert response.json()["sentence_count"] == 4
    assert calls == 1


def test_overlong_sentence_is_truncated_with_ascii_ellipsis_in_one_call(tmp_path):
    write_forecasts(tmp_path)
    calls = 0
    sentence = (
        "Rain showers may continue through the afternoon with locally heavy amounts and gusty "
        "winds across the region until midnight while isolated showers remain possible."
    )

    async def handler(request):
        nonlocal calls
        calls += 1
        return ollama_response([sentence])

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")

    assert response.status_code == 200
    result = response.json()
    assert result["sentence_count"] == 1
    assert len(result["sentences"][0]) <= 133
    assert result["sentences"][0].isascii()
    assert len(result["sentences"][0]) == 133
    assert result["sentences"][0].endswith("...")
    assert calls == 1


def test_repeated_invalid_output_is_not_cached(tmp_path):
    write_forecasts(tmp_path)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"message": {"content": "not json"}})

    app = create_app(make_settings(tmp_path), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/synopsis/message_summary")
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "invalid_ollama_response"
        assert client.get("/api/v1/forecasts/synopsis/message_summary").status_code == 502
        assert calls == 2


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
    records = [
        json.loads(line)
        for line in (tmp_path / "logs" / "summary_api.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert len(records) == 1
    assert records[0]["prompt"]
    assert records[0]["response_body"] is None
    assert error.__class__.__name__ in records[0]["request_error"]


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
    settings = load_settings(config_path)
    assert settings.forecast_dir == forecast_dir
    assert settings.ollama_num_ctx == 8192
    assert settings.diagnostic_log_path == (tmp_path / "logs" / "summary_api.jsonl").resolve()
    assert settings.diagnostic_log_enabled is True


def test_settings_load_configured_ollama_num_ctx(tmp_path):
    forecast_dir = tmp_path / "forecasts"
    forecast_dir.mkdir()
    config_path = tmp_path / "service.toml"
    config_path.write_text(
        '[ollama]\nurl = "http://localhost:11434"\nmodel = "test"\nnum_ctx = 4096\n'
        '[paths]\nforecast_dir = "forecasts"\n',
        encoding="utf-8",
    )
    assert load_settings(config_path).ollama_num_ctx == 4096


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