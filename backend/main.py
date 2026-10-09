from __future__ import annotations

from typing import Any, Dict, Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.cache import ReviewDatasetCache
from backend.config import Settings
from backend.errors import AppError, DatasetUnavailableError
from backend.ingestion import (
    SerpApiIngestionProvider,
    source_hint_key,
    validate_google_maps_url,
)
from backend.models import (
    ChatRequest,
    ChatResult,
    IngestRequest,
    IngestResult,
    ProviderDataset,
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


def success(data: Any, **meta: Any) -> dict[str, Any]:
    return {"data": data, "meta": meta}


def create_app(
    settings: Settings | None = None,
    ingestion_provider: IngestionProvider | None = None,
    question_answerer: QuestionAnswerer | None = None,
    cache: ReviewDatasetCache | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    ingestion_provider = ingestion_provider or SerpApiIngestionProvider(
        settings.serpapi_api_key,
        settings.provider_timeout_seconds,
        settings.max_reviews,
    )
    question_answerer = question_answerer or OpenAIQuestionAnswerer(
        settings.openai_api_key,
        settings.openai_model,
        settings.provider_timeout_seconds,
        settings.model_context_chars,
    )
    cache = cache or ReviewDatasetCache(
        settings.cache_ttl_seconds, settings.cache_max_entries
    )

    application = FastAPI(title="ReviewLens AI API", version=APP_VERSION)
    application.state.ingestion_provider = ingestion_provider
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
        validate_google_maps_url(payload.source_url)
        hint_key = source_hint_key(payload.source_url)
        result = cache.get_or_ingest(
            hint_key,
            lambda: ingestion_provider.ingest(payload.source_url),
        )
        response_data = result.model_dump(mode="json")
        response_data["dataset"]["sample_reviews"] = response_data["dataset"][
            "sample_reviews"
        ][:10]
        return success(
            response_data,
            cache_hit=result.cache_hit,
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


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
