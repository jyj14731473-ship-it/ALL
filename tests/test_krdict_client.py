from __future__ import annotations

import os
from types import TracebackType
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import DictApiFailure
from all_metaphor.krdict_client import KRDICT_SEARCH_ENDPOINT, KrdictClient


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return None

    def read(self) -> bytes:
        return self._payload


class FakeOpener:
    def __init__(self, outcomes: list[bytes | BaseException]) -> None:
        self.outcomes = outcomes
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Request, *, timeout: float) -> FakeResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)


def xml_payload(text: str) -> bytes:
    return text.encode("utf-8")


@pytest.fixture
def settings() -> RuntimeSettings:
    return RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )


def test_lookup_builds_request_and_parses_multiple_senses(settings: RuntimeSettings) -> None:
    opener = FakeOpener(
        [
            xml_payload(
                """
            <channel>
              <item>
                <sense>
                  <sense_no>1001</sense_no>
                  <definition>권리나 의무가 생김.</definition>
                </sense>
                <sense>
                  <sense_no>1002</sense_no>
                  <definition>일이나 관계가 이루어짐.</definition>
                </sense>
              </item>
            </channel>
            """
            )
        ]
    )
    client = KrdictClient(settings, opener=opener)

    meanings = client.lookup("성립")

    assert [(meaning.sense_id, meaning.definition) for meaning in meanings] == [
        ("1001", "권리나 의무가 생김."),
        ("1002", "일이나 관계가 이루어짐."),
    ]
    assert all(meaning.source == "standard_korean_language_dictionary" for meaning in meanings)

    request = opener.requests[0]
    parsed_url = urlparse(request.full_url)
    query = parse_qs(parsed_url.query)
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == KRDICT_SEARCH_ENDPOINT
    assert query == {
        "q": ["성립"],
        "key": ["test-krdict-key"],
        "part": ["word"],
        "sort": ["dict"],
        "start": ["1"],
        "num": ["10"],
    }


def test_lookup_parses_namespace_xml_and_missing_sense_id(settings: RuntimeSettings) -> None:
    opener = FakeOpener(
        [
            xml_payload(
                """
            <ns:channel xmlns:ns="https://example.test">
              <ns:sense>
                <ns:definition>어떤 일을 실제로 행함.</ns:definition>
              </ns:sense>
            </ns:channel>
            """
            )
        ]
    )
    client = KrdictClient(settings, opener=opener)

    meanings = client.lookup("이행")

    assert len(meanings) == 1
    assert meanings[0].sense_id is None
    assert meanings[0].definition == "어떤 일을 실제로 행함."


def test_lookup_skips_sense_without_definition(settings: RuntimeSettings) -> None:
    opener = FakeOpener(
        [
            xml_payload(
                """
            <channel>
              <sense><sense_no>1001</sense_no></sense>
              <sense><definition>뜻풀이</definition></sense>
            </channel>
            """
            )
        ]
    )
    client = KrdictClient(settings, opener=opener)

    meanings = client.lookup("단어")

    assert [(meaning.sense_id, meaning.definition) for meaning in meanings] == [(None, "뜻풀이")]


def test_lookup_returns_empty_list_for_no_results(settings: RuntimeSettings) -> None:
    opener = FakeOpener([b"<channel><total>0</total></channel>"])
    client = KrdictClient(settings, opener=opener)

    assert client.lookup("없는말") == []


def test_lookup_returns_empty_list_for_blank_lemma_without_api_call(
    settings: RuntimeSettings,
) -> None:
    opener = FakeOpener([])
    client = KrdictClient(settings, opener=opener)

    assert client.lookup("   ") == []
    assert opener.requests == []


def test_lookup_normalizes_cache_key_and_uses_cache(settings: RuntimeSettings) -> None:
    opener = FakeOpener(
        [
            xml_payload(
                """
            <channel>
              <sense>
                <sense_no>1</sense_no>
                <definition>정규화된 뜻.</definition>
              </sense>
            </channel>
            """
            )
        ]
    )
    client = KrdictClient(settings, opener=opener)

    first = client.lookup("  성립  ")
    first.append(first[0].model_copy(update={"definition": "caller mutation"}))
    first[0].definition = "mutated object"
    second = client.lookup("성립")

    assert len(opener.requests) == 1
    assert [(meaning.sense_id, meaning.definition) for meaning in second] == [("1", "정규화된 뜻.")]


def test_lookup_retries_failures_then_succeeds(settings: RuntimeSettings) -> None:
    sleep_calls: list[float] = []
    opener = FakeOpener(
        [
            URLError("temporary network failure"),
            TimeoutError("slow response"),
            xml_payload(
                """
            <channel>
              <sense><definition>성공한 뜻.</definition></sense>
            </channel>
            """,
            ),
        ]
    )
    client = KrdictClient(
        settings,
        opener=opener,
        sleep=sleep_calls.append,
        max_retries=3,
        backoff_initial_seconds=0.25,
    )

    meanings = client.lookup("성공")

    assert [meaning.definition for meaning in meanings] == ["성공한 뜻."]
    assert len(opener.requests) == 3
    assert sleep_calls == [0.25, 0.5]


def test_lookup_raises_dict_api_failure_after_retries_without_secret() -> None:
    settings = RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key="super-secret-key",
    )
    sleep_calls: list[float] = []
    opener = FakeOpener(
        [
            URLError("super-secret-key leaked by lower layer"),
            URLError("super-secret-key leaked by lower layer"),
            URLError("super-secret-key leaked by lower layer"),
        ]
    )
    client = KrdictClient(
        settings,
        opener=opener,
        sleep=sleep_calls.append,
        max_retries=2,
        backoff_initial_seconds=1.0,
    )

    with pytest.raises(DictApiFailure) as exc_info:
        client.lookup("실패")

    message = str(exc_info.value)
    assert "super-secret-key" not in message
    assert "lemma='실패'" in message
    assert len(opener.requests) == 3
    assert sleep_calls == [1.0, 2.0]
    assert exc_info.value.retryable is True


def test_lookup_passes_timeout_to_urlopen(settings: RuntimeSettings) -> None:
    opener = FakeOpener([b"<channel />"])
    client = KrdictClient(settings, opener=opener, timeout_seconds=3.5)

    client.lookup("시간")

    assert opener.timeouts == [3.5]


def test_lookup_retries_malformed_xml(settings: RuntimeSettings) -> None:
    sleep_calls: list[float] = []
    opener = FakeOpener(
        [
            b"<channel>",
            xml_payload("<channel><sense><definition>복구됨.</definition></sense></channel>"),
        ]
    )
    client = KrdictClient(
        settings,
        opener=opener,
        sleep=sleep_calls.append,
        max_retries=1,
        backoff_initial_seconds=0.1,
    )

    meanings = client.lookup("복구")

    assert [meaning.definition for meaning in meanings] == ["복구됨."]
    assert sleep_calls == [0.1]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout_seconds": 0.0}, "timeout_seconds must be positive"),
        ({"max_retries": -1}, "max_retries must be non-negative"),
        ({"backoff_initial_seconds": -0.1}, "backoff_initial_seconds must be non-negative"),
    ],
)
def test_client_rejects_invalid_retry_settings(
    settings: RuntimeSettings,
    kwargs: dict[str, float | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        KrdictClient(settings, **kwargs)


@pytest.mark.integration
def test_lookup_with_real_krdict_api_smoke() -> None:
    if os.environ.get("RUN_KRDICT_INTEGRATION") != "1":
        pytest.skip("Set RUN_KRDICT_INTEGRATION=1 to call the real KRDICT API.")
    api_key = os.environ.get("KRDICT_API_KEY")
    if api_key is None or api_key.strip() == "":
        pytest.skip("KRDICT_API_KEY is required for the real KRDICT API smoke test.")

    settings = RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key=api_key,
    )
    meanings = KrdictClient(settings).lookup("사랑")

    assert isinstance(meanings, list)
