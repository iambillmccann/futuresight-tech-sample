from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List
from urllib.parse import parse_qs, unquote, urlparse
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="ReviewLens AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_CACHE_SIZE = 50
CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = Lock()

SAMPLE_REVIEWS: List[Dict[str, Any]] = [
    {
        "review_id": "r1",
        "rating": 5,
        "author": "Sarah M.",
        "date": "2024-01-18",
        "text": "Best sounding in the city! The eggs Benedict were perfectly poached.",
    },
    {
        "review_id": "r2",
        "rating": 4,
        "author": "James Chen",
        "date": "2024-01-15",
        "text": "Excellent coffee and atmosphere. Bit of a wait on Sundays.",
    },
    {
        "review_id": "r3",
        "rating": 5,
        "author": "Elena K.",
        "date": "2024-01-12",
        "text": "The courtyard toast with avocado mash is life changing.",
    },
    {
        "review_id": "r4",
        "author": "Mark T.",
        "date": "2024-01-10",
        "rating": 4,
        "text": "Professional staff and consistent food quality. My go to brunch spot.",
    },
    {
        "review_id": "r5",
        "author": "Julia R.",
        "date": "2024-01-09",
        "rating": 3,
        "text": "Food was great but the music was slightly too loud for a conversation.",
    },
    {
        "review_id": "r6",
        "author": "Alex P.",
        "date": "2024-01-08",
        "rating": 2,
        "text": "Usually a long wait, even on weekdays. Plan ahead.",
    },
    {
        "review_id": "r7",
        "author": "Taylor L.",
        "date": "2024-01-07",
        "rating": 4,
        "text": "A bit pricey for what you get, but the food is good.",
    },
    {
        "review_id": "r8",
        "author": "Priya S.",
        "date": "2024-01-05",
        "rating": 4,
        "text": "Very loud inside. Hard to have a conversation.",
    },
]

BUSINESS_NAME = "Blue Bottle Coffee — Mint Plaza"
SOURCE_PLATFORM = "Google Maps"


def normalize_source_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported.")
    host = parsed.netloc.lower()
    if "google.com" not in host and "maps.google" not in host:
        raise ValueError("Only Google Maps URLs are supported.")

    path = unquote(parsed.path).lower()
    match = re.search(r"/place/([^/?#]+)", path) or re.search(r"/maps/place/([^/?#]+)", path)
    if match:
        slug = match.group(1)
    else:
        params = parse_qs(parsed.query)
        place_id = params.get("place_id", [""])[0] or params.get("q", [""])[0]
        slug = place_id or host + path
    normalized = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    return f"google-maps:{normalized or 'source'}"


def build_source_dataset(source_url: str, source_key: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    summary = {
        "review_count": 1240,
        "average_rating": 4.3,
        "rating_distribution": {"5": 47, "4": 30, "3": 13, "2": 7, "1": 3},
        "earliest_review": "2023-01-01",
        "latest_review": "2024-10-24",
    }
    return {
        "source_key": source_key,
        "source_url": source_url,
        "platform": SOURCE_PLATFORM,
        "business_name": BUSINESS_NAME,
        "ingested_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=CACHE_TTL_SECONDS)).isoformat(),
        "total_reviews": summary["review_count"],
        "sample_reviews": SAMPLE_REVIEWS,
        "summary": summary,
    }


def evaluate_scope(question: str) -> Dict[str, Any]:
    lowered = question.lower()
    disallowed = [
        "weather",
        "news",
        "stock",
        "amazon",
        "starbucks",
        "competitor",
        "other business",
        "generic knowledge",
        "ignore previous instructions",
        "system prompt",
        "who are you",
    ]
    if any(term in lowered for term in disallowed):
        return {"allowed": False, "reason": "This question asks about sources or knowledge outside the active Google Maps dataset."}

    if "google maps" in lowered and "amazon" in lowered:
        return {"allowed": False, "reason": "This question spans multiple review platforms and is outside the active dataset."}

    return {"allowed": True, "reason": "Question stays within the active source."}


def build_answer(question: str, dataset: Dict[str, Any]) -> Dict[str, Any]:
    prompt = question.lower()
    positive_hits = [
        review for review in dataset["sample_reviews"]
        if any(word in review["text"].lower() for word in ["coffee", "food", "atmosphere", "staff", "brunch", "toast", "eggs"])
    ]
    negative_hits = [
        review for review in dataset["sample_reviews"]
        if any(word in review["text"].lower() for word in ["wait", "loud", "price", "crowded", "noise", "conversation"])
    ]

    if "like most" in prompt or "favorite" in prompt or "best" in prompt:
        answer = (
            "Customers most frequently praise the quality of the food and coffee, especially the eggs Benedict, brunch items, and overall atmosphere. "
            "The strongest positive signal is a welcoming setting paired with consistent execution."
        )
        evidence = positive_hits[:3]
        confidence = 0.92
    elif "complaint" in prompt or "common complaints" in prompt or "problems" in prompt:
        answer = (
            "The most common complaints are long wait times, limited seating, higher prices, and noise during busy periods. "
            "A few reviewers also mention that the room can get loud enough to make conversation difficult."
        )
        evidence = negative_hits[:3]
        confidence = 0.88
    elif "theme" in prompt or "what people mention" in prompt:
        answer = (
            "Across the reviews, recurring themes are strong coffee, well-executed brunch food, a pleasant cafe atmosphere, and occasional friction from wait times and noise."
        )
        evidence = dataset["sample_reviews"][:4]
        confidence = 0.9
    else:
        answer = (
            "Based on the current dataset, customers consistently highlight the quality of the coffee and brunch menu, while waiting time and noise are the main friction points."
        )
        evidence = dataset["sample_reviews"][:3]
        confidence = 0.86

    return {
        "answer": answer,
        "confidence": confidence,
        "matching_reviews": [
            {
                "review_id": review["review_id"],
                "author": review["author"],
                "text": review["text"],
                "rating": review["rating"],
            }
            for review in evidence
        ],
    }


class IngestRequest(BaseModel):
    source_url: str = Field(..., min_length=10)

    @field_validator("source_url")
    @classmethod
    def validate_google_maps_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http/https URLs are allowed.")
        host = parsed.netloc.lower()
        if "google.com" not in host and "maps.google" not in host:
            raise ValueError("Only Google Maps URLs are supported in Milestone 1.")
        return value


class ChatRequest(BaseModel):
    source_key: str
    question: str = Field(..., min_length=1)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest")
def ingest_reviews(payload: IngestRequest) -> Dict[str, Any]:
    try:
        source_key = normalize_source_url(payload.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with CACHE_LOCK:
        if source_key in CACHE:
            entry = CACHE[source_key]
            if datetime.fromisoformat(entry["expires_at"]) > datetime.now(timezone.utc):
                return {
                    "source": {
                        "source_key": source_key,
                        "business_name": entry["business_name"],
                        "platform": entry["platform"],
                        "source_url": entry["source_url"],
                    },
                    "dataset": {
                        "total_reviews": entry["total_reviews"],
                        "sample_reviews": entry["sample_reviews"],
                        "summary": entry["summary"],
                    },
                    "cache_hit": True,
                }

        dataset = build_source_dataset(payload.source_url, source_key)
        CACHE[source_key] = dataset
        if len(CACHE) > MAX_CACHE_SIZE:
            oldest_key = next(iter(CACHE))
            del CACHE[oldest_key]
        return {
            "source": {
                "source_key": source_key,
                "business_name": dataset["business_name"],
                "platform": dataset["platform"],
                "source_url": dataset["source_url"],
            },
            "dataset": {
                "total_reviews": dataset["total_reviews"],
                "sample_reviews": dataset["sample_reviews"],
                "summary": dataset["summary"],
            },
            "cache_hit": False,
        }


@app.post("/api/chat")
def ask_question(payload: ChatRequest) -> Dict[str, Any]:
    with CACHE_LOCK:
        dataset = CACHE.get(payload.source_key)

    if not dataset:
        raise HTTPException(status_code=404, detail="No ingested dataset found for the selected source.")

    scope_result = evaluate_scope(payload.question)
    if not scope_result["allowed"]:
        return {
            "status": "refused",
            "scope_guard": scope_result,
            "answer": "Out of scope: I can only answer questions about the active Google Maps reviews for Blue Bottle Coffee — Mint Plaza.",
            "matching_reviews": [],
            "confidence": 0.0,
        }

    answer = build_answer(payload.question, dataset)
    return {
        "status": "ok",
        "scope_guard": scope_result,
        "answer": answer["answer"],
        "matching_reviews": answer["matching_reviews"],
        "confidence": answer["confidence"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
