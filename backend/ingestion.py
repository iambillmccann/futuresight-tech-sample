from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse, urlunparse

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
        raise InvalidSourceError(
            "Only google.com Google Maps URLs or maps.app.goo.gl share links are supported."
        )
    if "/maps" not in parsed.path and host != "maps.google.com":
        raise InvalidSourceError("The URL must identify a Google Maps location.")


SHARE_LINK_CODE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SHARE_LINK_MAX_REDIRECTS = 3
SHARE_LINK_MAX_LOCATION_LENGTH = 8_192
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def google_share_link_url(source_url: str) -> str | None:
    """Return a rebuilt canonical share URL, or None when the URL is not a share link."""
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host == "maps.app.goo.gl" and len(segments) == 1:
        prefix, code = "https://maps.app.goo.gl/", segments[0]
    elif host == "goo.gl" and len(segments) == 2 and segments[0] == "maps":
        prefix, code = "https://goo.gl/maps/", segments[1]
    elif host in {"maps.app.goo.gl", "goo.gl"}:
        raise InvalidSourceError("The Google Maps share link is not in a supported format.")
    else:
        return None
    if parsed.scheme not in {"http", "https"}:
        raise InvalidSourceError("Only http and https Google Maps URLs are supported.")
    if parsed.username or parsed.password:
        raise InvalidSourceError("Google Maps URLs cannot contain credentials.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidSourceError("The Google Maps share link is not in a supported format.") from exc
    if port is not None or not SHARE_LINK_CODE.match(code):
        raise InvalidSourceError("The Google Maps share link is not in a supported format.")
    return prefix + code


class GoogleShareLinkResolver:
    """Resolves Google Maps share links by reading only redirect headers from fixed Google hosts."""

    def __init__(self, timeout_seconds: int, client: httpx.Client | None = None) -> None:
        self._timeout = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def resolve(self, share_url: str) -> str:
        current = share_url
        for _ in range(SHARE_LINK_MAX_REDIRECTS):
            try:
                response = self._client.send(
                    self._client.build_request("GET", current, timeout=self._timeout),
                    follow_redirects=False,
                    stream=True,
                )
                response.close()
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    "SHARE_LINK_TIMEOUT",
                    "Google Maps did not respond while opening the share link. Please try again.",
                    504,
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(
                    "SHARE_LINK_UNAVAILABLE",
                    "The Google Maps share link could not be opened. Please try again.",
                    502,
                ) from exc

            location = response.headers.get("location", "")
            if response.status_code not in REDIRECT_STATUSES or not location:
                if response.status_code == 404:
                    raise InvalidSourceError(
                        "This Google Maps share link was not found or has expired."
                    )
                raise ProviderError(
                    "SHARE_LINK_UNRESOLVED",
                    "The Google Maps share link could not be resolved. "
                    "Open it in Google Maps and paste the full place URL instead.",
                    422,
                )
            if len(location) > SHARE_LINK_MAX_LOCATION_LENGTH:
                raise ProviderError(
                    "SHARE_LINK_UNRESOLVED",
                    "The Google Maps share link could not be resolved.",
                    422,
                )
            target = urljoin(current, location)
            next_share_link = google_share_link_url(target)
            if next_share_link:
                current = next_share_link
                continue
            try:
                validate_google_maps_url(target)
            except InvalidSourceError as exc:
                raise InvalidSourceError(
                    "The share link does not point to a Google Maps location."
                ) from exc
            return target
        raise ProviderError(
            "SHARE_LINK_UNRESOLVED",
            "The Google Maps share link redirected too many times.",
            422,
        )


def normalized_url_key(source_url: str) -> str:
    validate_google_maps_url(source_url)
    parsed = urlparse(source_url)
    query = parse_qs(parsed.query, keep_blank_values=False)
    retained_query = []
    for key in ("q", "query", "place_id", "data_id", "ftid"):
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
    if query.get("ftid") and re.fullmatch(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+", query["ftid"][0]):
        return "data_id", query["ftid"][0]
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


class SerpApiClient:
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

        if response.status_code == 401:
            raise ProviderError(
                "PROVIDER_AUTHENTICATION_FAILED",
                "The review provider credentials are invalid. Please contact the app administrator.",
                503,
            )
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


class SerpApiIngestionProvider(SerpApiClient):
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


def amazon_product_asin(source_url: str) -> str:
    try:
        parsed = urlparse(source_url)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"amazon.com", "www.amazon.com"}
            and not parsed.username
            and not parsed.password
            and parsed.port in {None, 80, 443}
        )
    except ValueError as exc:
        raise InvalidSourceError("The Amazon product URL is invalid.") from exc
    if not valid:
        raise InvalidSourceError(
            "Use a full amazon.com product URL without credentials or custom ports."
        )
    match = re.fullmatch(
        r"/(?:[^/]+/)?dp/([A-Za-z0-9]{10})(?:/.*)?"
        r"|/gp/product/([A-Za-z0-9]{10})(?:/.*)?",
        parsed.path,
    )
    if not match:
        raise InvalidSourceError(
            "Use an amazon.com product URL containing /dp/ASIN or /gp/product/ASIN."
        )
    return (match.group(1) or match.group(2)).upper()


def is_amazon_source(source_url: str) -> bool:
    try:
        return urlparse(source_url).hostname in {"amazon.com", "www.amazon.com"}
    except ValueError as exc:
        raise InvalidSourceError("The source URL is invalid.") from exc


def amazon_source_key(asin: str) -> str:
    return f"amazon:amazon.com:asin:{asin}"


class SerpApiAmazonIngestionProvider(SerpApiClient):
    def ingest(self, source_url: str) -> ProviderDataset:
        asin = amazon_product_asin(source_url)
        if not self._api_key:
            raise ConfigurationError("SERPAPI_API_KEY")
        payload = self._request(
            {
                "engine": "amazon_product",
                "asin": asin,
                "amazon_domain": "amazon.com",
                "language": "en_US",
            }
        )
        product = payload.get("product_results")
        if (
            not isinstance(product, dict)
            or product.get("asin") != asin
            or not isinstance(product.get("title"), str)
            or not product["title"].strip()
        ):
            raise ProviderError(
                "PROVIDER_MALFORMED_RESPONSE",
                "The review provider did not return the requested Amazon product.",
                502,
            )
        information = payload.get("reviews_information", {})
        if not isinstance(information, dict):
            raise ProviderError(
                "PROVIDER_MALFORMED_RESPONSE",
                "The review provider returned invalid Amazon review data.",
                502,
            )
        raw_reviews = information.get("authors_reviews", [])
        if not isinstance(raw_reviews, list):
            raise ProviderError(
                "PROVIDER_MALFORMED_RESPONSE",
                "The review provider returned invalid Amazon review data.",
                502,
            )
        reviews_by_id: dict[str, Review] = {}
        skipped = 0
        for raw_review in raw_reviews:
            normalized = self._normalize_amazon_review(raw_review, asin)
            if normalized is None:
                skipped += 1
                continue
            reviews_by_id.setdefault(normalized.review_id, normalized)
            if len(reviews_by_id) >= self._max_reviews:
                break
        if not reviews_by_id:
            raise ProviderError(
                "NO_USABLE_REVIEWS",
                "Reviews are not available for this item. Please try another Amazon product or Google Maps location.",
                422,
            )
        return ProviderDataset(
            source=Source(
                source_key=amazon_source_key(asin),
                business_name=product["title"].strip(),
                platform="Amazon",
                source_url=f"https://www.amazon.com/dp/{asin}",
                provider_id=asin,
            ),
            reviews=list(reviews_by_id.values()),
            skipped_review_count=skipped,
            warnings=[
                "Limited Amazon coverage: only customer reviews visible on the product "
                "page were retrieved. This is not the full review history; counts and "
                "ratings describe only the cached sample. Reviews may cover product variants."
            ],
        )

    @staticmethod
    def _normalize_amazon_review(raw_review: Any, asin: str) -> Review | None:
        if not isinstance(raw_review, dict):
            return None
        text = raw_review.get("text")
        rating = raw_review.get("rating")
        if (
            not isinstance(text, str)
            or not text.strip()
            or isinstance(rating, bool)
            or not isinstance(rating, (int, float))
            or not 1 <= rating <= 5
        ):
            return None
        author = raw_review.get("author")
        author = author if isinstance(author, str) and author.strip() else "Anonymous reviewer"
        raw_date = raw_review.get("date")
        date = raw_date if isinstance(raw_date, str) and raw_date.strip() else None
        if date:
            try:
                date = datetime.strptime(date, "%B %d, %Y").date().isoformat()
            except ValueError:
                pass  # Preserve unrecognized provider dates without inventing one.
        link = raw_review.get("link")
        review_url = None
        if isinstance(link, str):
            try:
                parsed = urlparse(link)
                if (
                    parsed.scheme == "https"
                    and parsed.hostname in {"amazon.com", "www.amazon.com"}
                    and not parsed.username
                    and not parsed.password
                    and parsed.port in {None, 443}
                ):
                    review_url = link
            except ValueError:
                pass  # An unusable source link does not invalidate the review text.
        identity = f"{asin}|{author}|{date}|{text.strip()}".encode()
        review_id = raw_review.get("review_id")
        return Review(
            review_id=(
                review_id
                if isinstance(review_id, str) and review_id.strip()
                else hashlib.sha256(identity).hexdigest()[:24]
            ),
            author=author,
            date=date,
            rating=float(rating),
            text=text.strip()[:5_000],
            review_url=review_url,
        )
