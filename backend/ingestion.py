from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse

import httpx

from backend.errors import ConfigurationError, InvalidSourceError, ProviderError
from backend.models import ProviderDataset, Review, Source

SERPAPI_URL = "https://serpapi.com/search.json"
GOOGLE_HOST_PATTERN = re.compile(r"(^|\.)google\.com$")


def validate_google_maps_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"}:
        raise InvalidSourceError("Only http and https Google Maps URLs are supported.")
    if parsed.username or parsed.password:
        raise InvalidSourceError("Google Maps URLs cannot contain credentials.")
    if not GOOGLE_HOST_PATTERN.search(host):
        raise InvalidSourceError("Only full google.com Google Maps URLs are supported.")
    if "/maps" not in parsed.path and host != "maps.google.com":
        raise InvalidSourceError("The URL must identify a Google Maps location.")


def normalized_url_key(source_url: str) -> str:
    validate_google_maps_url(source_url)
    parsed = urlparse(source_url)
    query = parse_qs(parsed.query, keep_blank_values=False)
    retained_query = []
    for key in ("q", "query", "place_id", "data_id"):
        for value in query.get(key, []):
            retained_query.append((key, value))
    normalized = urlunparse(
        (
            "https",
            (parsed.hostname or "").lower().rstrip("."),
            re.sub(r"/+", "/", unquote(parsed.path)).rstrip("/"),
            "",
            urlencode(retained_query),
            "",
        )
    )
    return f"google-maps:url:{hashlib.sha256(normalized.encode()).hexdigest()[:24]}"


def _explicit_provider_id(source_url: str) -> tuple[str, str] | None:
    parsed = urlparse(source_url)
    query = parse_qs(parsed.query)
    for key in ("place_id", "data_id"):
        if query.get(key):
            return key, query[key][0]
    data_match = re.search(r"!1s([^!]+)", unquote(parsed.path))
    if data_match:
        return "data_id", data_match.group(1)
    return None


def source_hint_key(source_url: str) -> str:
    explicit_id = _explicit_provider_id(source_url)
    if explicit_id:
        return f"google-maps:{explicit_id[0]}:{explicit_id[1]}"
    return normalized_url_key(source_url)


def _search_query(source_url: str) -> str:
    parsed = urlparse(source_url)
    query = parse_qs(parsed.query)
    query_value = query.get("q", query.get("query", [""]))[0]
    if query_value:
        return query_value
    match = re.search(r"/place/([^/]+)", unquote(parsed.path))
    if match:
        return match.group(1).replace("+", " ").strip()
    raise InvalidSourceError(
        "The Google Maps URL does not contain a resolvable place name or provider identifier."
    )


class SerpApiIngestionProvider:
    def __init__(
        self,
        api_key: str,
        timeout_seconds: int,
        max_reviews: int,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_reviews = max_reviews
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def ingest(self, source_url: str) -> ProviderDataset:
        validate_google_maps_url(source_url)
        if not self._api_key:
            raise ConfigurationError("SERPAPI_API_KEY")

        identifier = _explicit_provider_id(source_url)
        business_name: str | None = None
        if identifier is None:
            identifier, business_name = self._resolve_source(source_url)

        reviews: list[Review] = []
        skipped = 0
        warnings: list[str] = []
        page_token: str | None = None
        provider_metadata: dict[str, Any] = {}

        while len(reviews) < self._max_reviews:
            params: dict[str, Any] = {
                "engine": "google_maps_reviews",
                identifier[0]: identifier[1],
                "hl": "en",
            }
            if page_token:
                params["next_page_token"] = page_token
            try:
                payload = self._request(params)
            except ProviderError as exc:
                if not reviews:
                    raise
                warnings.append(
                    f"Review retrieval stopped early after an upstream error ({exc.code})."
                )
                break

            provider_metadata = provider_metadata or payload
            raw_reviews = payload.get("reviews")
            if not isinstance(raw_reviews, list):
                if not reviews:
                    raise ProviderError(
                        "PROVIDER_MALFORMED_RESPONSE",
                        "The review provider returned an invalid response.",
                        502,
                    )
                break

            for raw_review in raw_reviews:
                normalized = self._normalize_review(raw_review)
                if normalized is None:
                    skipped += 1
                    continue
                reviews.append(normalized)
                if len(reviews) >= self._max_reviews:
                    break

            pagination = payload.get("serpapi_pagination") or {}
            page_token = pagination.get("next_page_token")
            if not page_token or not raw_reviews:
                break

        if not reviews:
            raise ProviderError(
                "NO_USABLE_REVIEWS",
                "No usable text reviews were returned for this Google Maps source.",
                422,
            )

        place_info = provider_metadata.get("place_info") or {}
        business_name = (
            place_info.get("title")
            or place_info.get("name")
            or business_name
            or _search_query(source_url)
        )
        provider_id = (
            place_info.get("place_id")
            or place_info.get("data_id")
            or identifier[1]
        )
        provider_kind = "place_id" if place_info.get("place_id") else identifier[0]
        source = Source(
            source_key=f"google-maps:{provider_kind}:{provider_id}",
            source_url=source_url,
            business_name=str(business_name),
            provider_id=str(provider_id),
        )
        return ProviderDataset(
            source=source,
            reviews=reviews,
            skipped_review_count=skipped,
            warnings=warnings,
        )

    def _resolve_source(self, source_url: str) -> tuple[tuple[str, str], str]:
        payload = self._request(
            {
                "engine": "google_maps",
                "q": _search_query(source_url),
                "type": "search",
                "hl": "en",
            }
        )
        candidates = payload.get("local_results") or []
        if not candidates and payload.get("place_results"):
            candidates = [payload["place_results"]]
        if not candidates:
            raise ProviderError(
                "SOURCE_NOT_FOUND",
                "SerpApi could not resolve that Google Maps location.",
                422,
            )
        candidate = candidates[0]
        provider_id = candidate.get("place_id") or candidate.get("data_id")
        if not provider_id:
            raise ProviderError(
                "PROVIDER_MALFORMED_RESPONSE",
                "The review provider did not return a stable location identifier.",
                502,
            )
        kind = "place_id" if candidate.get("place_id") else "data_id"
        return (kind, str(provider_id)), str(
            candidate.get("title") or candidate.get("name") or _search_query(source_url)
        )

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.get(
                SERPAPI_URL,
                params={**params, "api_key": self._api_key},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "PROVIDER_TIMEOUT",
                "The review provider timed out. Please try again.",
                504,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "The review provider is temporarily unavailable.",
                502,
            ) from exc

        if response.status_code == 429:
            raise ProviderError(
                "PROVIDER_QUOTA_EXCEEDED",
                "The review provider rate limit or quota was reached. Please try later.",
                503,
            )
        if response.status_code >= 500:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "The review provider is temporarily unavailable.",
                502,
            )
        if response.status_code >= 400:
            raise ProviderError(
                "PROVIDER_REJECTED_SOURCE",
                "The review provider could not process that source.",
                422,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(
                "PROVIDER_MALFORMED_RESPONSE",
                "The review provider returned an invalid response.",
                502,
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderError(
                "PROVIDER_MALFORMED_RESPONSE",
                "The review provider returned an invalid response.",
                502,
            )
        if payload.get("error"):
            raise ProviderError(
                "PROVIDER_REJECTED_SOURCE",
                "The review provider could not process that source.",
                422,
            )
        return payload

    @staticmethod
    def _normalize_review(raw_review: Any) -> Review | None:
        if not isinstance(raw_review, dict):
            return None
        text = raw_review.get("snippet") or raw_review.get("text")
        rating = raw_review.get("rating")
        if not isinstance(text, str) or not text.strip():
            return None
        if not isinstance(rating, (int, float)) or not 1 <= float(rating) <= 5:
            return None
        user = raw_review.get("user") or {}
        author = user.get("name") if isinstance(user, dict) else None
        author = author or raw_review.get("author") or "Anonymous reviewer"
        date = raw_review.get("iso_date") or raw_review.get("date")
        review_id = raw_review.get("review_id")
        if not review_id:
            identity = f"{author}|{date}|{text}".encode()
            review_id = hashlib.sha256(identity).hexdigest()[:24]
        return Review(
            review_id=str(review_id),
            author=str(author),
            date=str(date) if date else None,
            rating=float(rating),
            text=text.strip()[:5_000],
            review_url=raw_review.get("link"),
        )
