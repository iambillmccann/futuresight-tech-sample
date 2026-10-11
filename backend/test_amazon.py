from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.errors import InvalidSourceError, ProviderError
from backend.ingestion import SerpApiAmazonIngestionProvider, amazon_product_asin
from backend.main import create_app
from backend.cache import ReviewDatasetCache
from backend.qa import OpenAIQuestionAnswerer, requests_unselected_platform
from backend.test_app import ALPHA_URL, FakeIngestionProvider, settings

ASIN = "B072MQ5BRX"
AMAZON_URL = f"https://www.amazon.com/dp/{ASIN}"


def product_payload(asin: str = ASIN) -> dict[str, Any]:
    return {
        "product_results": {
            "asin": asin,
            "title": "Test Coffee",
            "rating": 4.8,
            "reviews": 12_243,
        },
        "reviews_information": {
            "summary": {"text": "Do not use this generated product-wide summary."},
            "authors_reviews": [
                {
                    "text": "Dependable daily coffee.",
                    "rating": 5.0,
                    "date": "July 15, 2026",
                    "author": "May",
                    "product": {"flavor_name": "Colombia"},
                },
                {
                    "review_id": "second-review",
                    "text": "Too bitter for me.",
                    "rating": 3.0,
                    "date": "July 16, 2026",
                    "author": "Lee",
                    "link": "https://www.amazon.com/gp/customer-reviews/RTEST",
                },
            ],
        },
    }


@pytest.mark.parametrize(
    "url",
    [
        AMAZON_URL,
        f"https://amazon.com/Test-Coffee/dp/{ASIN}/ref=test?tag=tracking",
        f"https://www.amazon.com/gp/product/{ASIN}?ref=tracking",
        f"http://www.amazon.com/dp/{ASIN.lower()}",
    ],
)
def test_supported_product_urls_resolve_to_the_same_asin(url: str) -> None:
    assert amazon_product_asin(url) == ASIN


@pytest.mark.parametrize(
    "url",
    [
        f"https://amazon.com.evil.example/dp/{ASIN}",
        f"https://evilamazon.com/dp/{ASIN}",
        f"https://www.amazon.co.uk/dp/{ASIN}",
        f"https://www.amazon.com@127.0.0.1/dp/{ASIN}",
        f"https://user:password@www.amazon.com/dp/{ASIN}",
        f"https://www.amazon.com:8080/dp/{ASIN}",
        f"https://www.amazon.com:invalid/dp/{ASIN}",
        f"file://www.amazon.com/dp/{ASIN}",
        f"https://127.0.0.1/dp/{ASIN}",
        "https://www.amazon.com/s?k=coffee",
        "https://www.amazon.com/dp/SHORT",
        f"https://www.amazon.com/dp/{ASIN}EXTRA",
        "https://amzn.to/short",
    ],
)
def test_unsupported_amazon_urls_are_rejected(url: str) -> None:
    with pytest.raises(InvalidSourceError):
        amazon_product_asin(url)


def test_amazon_adapter_normalizes_only_individual_reviews_and_bounds_coverage() -> None:
    requests: list[httpx.Request] = []
    payload = product_payload()
    payload["reviews_information"]["authors_reviews"].extend(
        [
            payload["reviews_information"]["authors_reviews"][0],
            {"text": "", "rating": 5},
            {"text": "Invalid rating", "rating": 9},
            {"text": "Invalid boolean rating", "rating": True},
        ]
    )

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = SerpApiAmazonIngestionProvider("test-key", 2, 200, client)
        dataset = provider.ingest(AMAZON_URL)

    assert requests[0].url.host == "serpapi.com"
    assert requests[0].url.params["engine"] == "amazon_product"
    assert requests[0].url.params["asin"] == ASIN
    assert requests[0].url.params["amazon_domain"] == "amazon.com"
    assert dataset.source.platform == "Amazon"
    assert dataset.source.source_key == f"amazon:amazon.com:asin:{ASIN}"
    assert dataset.skipped_review_count == 3
    assert len(dataset.reviews) == 2
    assert dataset.reviews[0].date == "2026-07-15"
    assert dataset.reviews[0].review_url is None
    assert dataset.reviews[1].review_url == "https://www.amazon.com/gp/customer-reviews/RTEST"
    assert dataset.warnings and "not the full review history" in dataset.warnings[0]
    assert all("product-wide summary" not in review.text for review in dataset.reviews)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        bounded = SerpApiAmazonIngestionProvider("test-key", 2, 1, client).ingest(AMAZON_URL)
    assert len(bounded.reviews) == 1


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({}, "PROVIDER_MALFORMED_RESPONSE"),
        (product_payload("B000000000"), "PROVIDER_MALFORMED_RESPONSE"),
        (
            {"product_results": product_payload()["product_results"], "reviews_information": []},
            "PROVIDER_MALFORMED_RESPONSE",
        ),
        (
            {
                "product_results": product_payload()["product_results"],
                "reviews_information": {"authors_reviews": {}},
            },
            "PROVIDER_MALFORMED_RESPONSE",
        ),
        ({"product_results": product_payload()["product_results"]}, "NO_USABLE_REVIEWS"),
    ],
)
def test_amazon_missing_or_wrong_product_data_never_becomes_a_dataset(
    payload: dict[str, Any], expected_code: str
) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        provider = SerpApiAmazonIngestionProvider("test-key", 2, 20, client)
        with pytest.raises(ProviderError) as error:
            provider.ingest(AMAZON_URL)
    assert error.value.code == expected_code


@pytest.mark.parametrize(
    "review_information",
    [
        {},
        {"authors_reviews": []},
        {"authors_reviews": [{"text": "", "rating": 5}]},
    ],
)
def test_unavailable_amazon_reviews_return_a_friendly_api_message(
    review_information: dict[str, Any],
) -> None:
    payload = product_payload("B0HKSHKDG8")
    payload["reviews_information"] = review_information
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as provider_client:
        amazon = SerpApiAmazonIngestionProvider("test-key", 2, 200, provider_client)
        with TestClient(
            create_app(settings=settings(), amazon_ingestion_provider=amazon)
        ) as client:
            response = client.post(
                "/api/ingest",
                json={
                    "source_url": "https://www.amazon.com/dp/B0HKSHKDG8"
                    "?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1"
                },
            )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "NO_USABLE_REVIEWS",
            "message": (
                "Reviews are not available for this item. "
                "Please try another Amazon product or Google Maps location."
            ),
            "details": [],
        }
    }


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "PROVIDER_AUTHENTICATION_FAILED"), (429, "PROVIDER_QUOTA_EXCEEDED"),
     (503, "PROVIDER_UNAVAILABLE")],
)
def test_amazon_upstream_errors_remain_sanitized(status: int, code: str) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, json={"error": "upstream secret"})
        )
    ) as client:
        provider = SerpApiAmazonIngestionProvider("test-key", 2, 20, client)
        with pytest.raises(ProviderError) as error:
            provider.ingest(AMAZON_URL)
    assert error.value.code == code
    assert "upstream secret" not in error.value.message


def test_amazon_api_cache_refresh_browse_and_model_context_are_platform_isolated() -> None:
    ingestion_requests: list[httpx.Request] = []
    model_requests: list[dict[str, Any]] = []

    def ingest_response(request: httpx.Request) -> httpx.Response:
        ingestion_requests.append(request)
        return httpx.Response(200, json=product_payload(request.url.params["asin"]))

    def model_response(request: httpx.Request) -> httpx.Response:
        model_requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "status": "refused",
            "answer": "Only the active platform and entity's reviews are in scope.",
            "evidence_review_ids": [],
            "confidence": 0,
        })}}]})

    google = FakeIngestionProvider()
    with httpx.Client(transport=httpx.MockTransport(ingest_response)) as provider_client, \
            httpx.Client(transport=httpx.MockTransport(model_response)) as model_client:
        amazon = SerpApiAmazonIngestionProvider("test-key", 2, 200, provider_client)
        answerer = OpenAIQuestionAnswerer("test-key", "test-model", 2, 60_000, model_client)
        with TestClient(create_app(
            settings=settings(), ingestion_provider=google,
            amazon_ingestion_provider=amazon, question_answerer=answerer,
        )) as client:
            alpha = client.post("/api/ingest", json={"source_url": ALPHA_URL}).json()["data"]
            result = client.post("/api/ingest", json={"source_url": AMAZON_URL}).json()["data"]
            key = result["source"]["source_key"]
            assert result["source"]["platform"] == "Amazon"
            assert result["dataset"]["summary"]["ingestion_status"] == "partial"
            assert result["dataset"]["summary"]["average_rating"] == 4.0
            assert result["dataset"]["total_reviews"] == 2
            hit = client.post("/api/ingest", json={
                "source_url": f"https://amazon.com/Coffee/dp/{ASIN}?tag=tracking",
            }).json()["data"]
            assert hit["cache_hit"] is True
            assert len(ingestion_requests) == 1
            for source_key, question, platform in [
                (key, "What do Google Maps reviews say?", "Amazon"),
                (alpha["source"]["source_key"], "What do Amazon reviews say?", "Google Maps"),
            ]:
                response = client.post("/api/chat", json={
                    "source_key": source_key, "question": question,
                })
                assert response.json()["data"]["status"] == "refused"
                prompt = model_requests[-1]["messages"][0]["content"]
                context = model_requests[-1]["messages"][1]["content"]
                assert f"- Platform: {platform}" in prompt
                assert "unselected platform must be refused" in prompt
                if platform == "Amazon":
                    assert "Limited Amazon coverage" in prompt
                    assert "Dependable daily coffee." in context
                    assert "Excellent coffee and kind staff." not in context
                    assert "product-wide summary" not in context
                else:
                    assert "Excellent coffee and kind staff." in context
                    assert "Dependable daily coffee." not in context
            browsed = client.get("/api/reviews", params={"source_key": key, "rating": 3})
            assert browsed.json()["data"]["reviews"][0]["review_id"] == "second-review"
            assert client.post("/api/refresh", json={"source_key": key}).status_code == 200
            assert len(ingestion_requests) == 2
            assert google.calls == 1
            invalid = client.post("/api/ingest", json={
                "source_url": f"https://www.amazon.com:8080/dp/{ASIN}",
            })
            assert invalid.status_code == 400
            assert len(ingestion_requests) == 2


@pytest.mark.parametrize(
    ("platform", "question", "expected"),
    [
        ("Amazon", "What do Google Maps reviewers say about this coffee?", True),
        ("Amazon", "What do google reviews say?", True),
        ("Amazon", "What do Amazon reviewers say?", False),
        ("Google Maps", "What do AMAZON reviewers say?", True),
        ("Google Maps", "What do Google Maps reviewers say?", False),
    ],
)
def test_explicit_unselected_platform_requests_are_identified(
    platform: str, question: str, expected: bool
) -> None:
    assert requests_unselected_platform(question, platform) is expected


def test_model_cannot_relabel_amazon_reviews_as_google_maps_evidence() -> None:
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=product_payload())
    )) as provider_client:
        amazon = SerpApiAmazonIngestionProvider("key", 2, 200, provider_client)
        result = ReviewDatasetCache(60, 5).get_or_ingest(
            "amazon", lambda: amazon.ingest(AMAZON_URL)
        )
    model_payload = {"choices": [{"message": {"content": json.dumps({
        "status": "ok",
        "answer": "Google Maps reviewers praise the coffee.",
        "evidence_review_ids": [result.dataset.sample_reviews[0].review_id],
        "confidence": 0.9,
    })}}]}
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=model_payload)
    )) as model_client:
        answer = OpenAIQuestionAnswerer("key", "model", 2, 60_000, model_client).answer(
            "What do Google Maps reviewers say about this coffee?",
            result,
            result.dataset.sample_reviews,
        )
    assert answer.status == "refused"
    assert answer.matching_reviews == []
    assert answer.confidence == 0
    assert "active Amazon reviews" in answer.answer


def test_different_amazon_products_do_not_share_cached_reviews() -> None:
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        asin = request.url.params["asin"]
        requests.append(asin)
        payload = product_payload(asin)
        payload["reviews_information"]["authors_reviews"][0]["text"] = f"Review for {asin}"
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(respond)) as provider_client:
        amazon = SerpApiAmazonIngestionProvider("key", 2, 200, provider_client)
        with TestClient(create_app(settings=settings(), amazon_ingestion_provider=amazon)) as client:
            first = client.post("/api/ingest", json={"source_url": AMAZON_URL}).json()["data"]
            second = client.post("/api/ingest", json={
                "source_url": "https://www.amazon.com/dp/B000000000",
            }).json()["data"]
            assert first["source"]["source_key"] != second["source"]["source_key"]
            for result, asin in [(first, ASIN), (second, "B000000000")]:
                response = client.get("/api/reviews", params={
                    "source_key": result["source"]["source_key"],
                })
                assert response.json()["data"]["reviews"][0]["text"] == f"Review for {asin}"
            assert requests == [ASIN, "B000000000"]


def test_amazon_preserves_unknown_dates_and_rejects_unsafe_review_links() -> None:
    normalized = SerpApiAmazonIngestionProvider._normalize_amazon_review({
        "text": "Real customer text.",
        "rating": 4,
        "date": "Yesterday",
        "link": "javascript:alert(1)",
    }, ASIN)
    assert normalized is not None
    assert normalized.date == "Yesterday"
    assert normalized.review_url is None


def test_amazon_timeout_produces_a_sanitized_error() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive transport details")

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        provider = SerpApiAmazonIngestionProvider("key", 2, 20, client)
        with pytest.raises(ProviderError) as error:
            provider.ingest(AMAZON_URL)
    assert error.value.code == "PROVIDER_TIMEOUT"
    assert "sensitive" not in error.value.message
