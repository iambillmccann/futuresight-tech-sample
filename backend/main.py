from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Protocol

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.cache import ReviewDatasetCache
from backend.config import Settings
from backend.errors import AppError, DatasetUnavailableError
from backend.ingestion import (
    GoogleShareLinkResolver,
    SerpApiAmazonIngestionProvider,
    SerpApiIngestionProvider,
    amazon_product_asin,
    amazon_source_key,
    google_share_link_url,
    is_amazon_source,
    source_hint_key,
    validate_google_maps_url,
)
from backend.models import (
    ChatRequest,
    ChatResult,
    IngestRequest,
    IngestResult,
    ProviderDataset,
    RefreshRequest,
    Review,
)
from backend.qa import OpenAIQuestionAnswerer

APP_VERSION = "0.2.0"


class IngestionProvider(Protocol):
    def ingest(self, source_url: str) -> ProviderDataset: ...


class QuestionAnswerer(Protocol):
    def answer(
        self, question: str, result: IngestResult, reviews: list[Review]
    ) -> ChatResult: ...


class ShareLinkResolver(Protocol):
    def resolve(self, share_url: str) -> str: ...


def success(data: Any, **meta: Any) -> dict[str, Any]:
    return {"data": data, "meta": meta}


def create_app(
    settings: Settings | None = None,
    ingestion_provider: IngestionProvider | None = None,
    question_answerer: QuestionAnswerer | None = None,
    cache: ReviewDatasetCache | None = None,
    amazon_ingestion_provider: IngestionProvider | None = None,
    share_link_resolver: ShareLinkResolver | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    share_link_resolver = share_link_resolver or GoogleShareLinkResolver(
        settings.provider_timeout_seconds
    )
    ingestion_provider = ingestion_provider or SerpApiIngestionProvider(
        settings.serpapi_api_key,
        settings.provider_timeout_seconds,
        settings.max_reviews,
    )
    amazon_ingestion_provider = (
        amazon_ingestion_provider
        or SerpApiAmazonIngestionProvider(
            settings.serpapi_api_key,
            settings.provider_timeout_seconds,
            settings.max_reviews,
        )
    )
    question_answerer = question_answerer or OpenAIQuestionAnswerer(
        settings.openai_api_key,
        settings.openai_model,
        settings.provider_timeout_seconds,
        settings.model_context_chars,
    )
    cache = cache or ReviewDatasetCache(
        settings.cache_ttl_seconds,
        settings.cache_max_entries,
        max_reviews=settings.max_reviews,
    )

    application = FastAPI(title="ReviewLens AI API", version=APP_VERSION)
    application.state.ingestion_provider = ingestion_provider
    application.state.amazon_ingestion_provider = amazon_ingestion_provider
    application.state.question_answerer = question_answerer
    application.state.review_cache = cache
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": [],
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"][1:]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request payload is invalid.",
                    "details": details,
                }
            },
        )

    @application.get("/health")
    @application.get("/api/health")
    def health() -> Dict[str, Any]:
        return success({"status": "ok"})

    @application.get("/ready")
    def ready() -> Dict[str, Any]:
        return success({"status": "ready"})

    @application.get("/version")
    def version() -> Dict[str, Any]:
        return success({"version": APP_VERSION})

    @application.post("/api/ingest")
    def ingest_reviews(payload: IngestRequest) -> Dict[str, Any]:
        source_url = payload.source_url
        share_url = google_share_link_url(source_url)
        if share_url:
            source_url = share_link_resolver.resolve(share_url)
        if is_amazon_source(source_url):
            hint_key = amazon_source_key(amazon_product_asin(source_url))
            provider = amazon_ingestion_provider
        else:
            validate_google_maps_url(source_url)
            hint_key = source_hint_key(source_url)
            provider = ingestion_provider
        result = cache.get_or_ingest(
            hint_key,
            lambda: provider.ingest(source_url),
        )
        response_data = result.model_dump(mode="json")
        response_data["dataset"]["sample_reviews"] = response_data["dataset"][
            "sample_reviews"
        ][:10]
        return success(
            response_data,
            cache_hit=result.cache_hit,
        )

    @application.post("/api/refresh")
    def refresh_reviews(payload: RefreshRequest) -> Dict[str, Any]:
        result = cache.refresh(
            payload.source_key,
            lambda source_url: (
                amazon_ingestion_provider
                if is_amazon_source(source_url)
                else ingestion_provider
            ).ingest(source_url),
        )
        if result is None:
            raise DatasetUnavailableError()
        response_data = result.model_dump(mode="json")
        response_data["dataset"]["sample_reviews"] = response_data["dataset"][
            "sample_reviews"
        ][:10]
        return success(response_data, cache_hit=False)

    @application.get("/api/reviews")
    def browse_reviews(
        source_key: str = Query(min_length=1, max_length=512),
        page: int = Query(default=1, ge=1, le=10_000),
        page_size: int = Query(default=25, ge=1, le=200),
        rating: Optional[int] = Query(default=None, ge=1, le=5),
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        if start_date and end_date and start_date > end_date:
            raise AppError(
                "INVALID_DATE_RANGE",
                "The start date must be on or before the end date.",
                422,
            )
        result = cache.get(source_key)
        if result is None:
            raise DatasetUnavailableError()

        reviews = result.dataset.sample_reviews
        if rating is not None:
            reviews = [review for review in reviews if round(review.rating) == rating]
        if start_date or end_date:
            reviews = [
                review
                for review in reviews
                if _review_is_within_dates(review.date, start_date, end_date)
            ]
        start = (page - 1) * page_size
        return success(
            {
                "source_key": result.source.source_key,
                "reviews": [
                    review.model_dump(mode="json")
                    for review in reviews[start : start + page_size]
                ],
                "total_reviews": len(reviews),
                "page": page,
                "page_size": page_size,
            }
        )

    @application.post("/api/chat")
    def ask_question(payload: ChatRequest) -> Dict[str, Any]:
        result = cache.get(payload.source_key)
        if result is None:
            raise DatasetUnavailableError()
        reviews = result.dataset.sample_reviews
        answer = question_answerer.answer(payload.question, result, reviews)
        return success(answer.model_dump(mode="json"))

    return application


def _review_is_within_dates(
    review_date: str | None,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    if not review_date:
        return False
    try:
        parsed_date = date.fromisoformat(review_date[:10])
    except ValueError:
        return False
    return (start_date is None or parsed_date >= start_date) and (
        end_date is None or parsed_date <= end_date
    )


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
