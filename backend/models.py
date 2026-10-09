from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    author: str
    date: Optional[str] = None
    rating: float = Field(ge=1, le=5)
    text: str
    review_url: Optional[str] = None


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str
    business_name: str
    platform: Literal["Google Maps"] = "Google Maps"
    source_url: str
    provider_id: Optional[str] = None


class DatasetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_count: int
    average_rating: float
    rating_distribution: Dict[str, int]
    earliest_review: Optional[str]
    latest_review: Optional[str]
    skipped_review_count: int
    ingestion_status: Literal["complete", "partial"]


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_reviews: int
    sample_reviews: List[Review]
    summary: DatasetSummary


class IngestResult(BaseModel):
    source: Source
    dataset: Dataset
    cache_hit: bool
    fetched_at: datetime
    expires_at: datetime
    warnings: List[str] = Field(default_factory=list)


class EvidenceReview(BaseModel):
    review_id: str
    author: str
    date: Optional[str]
    rating: float
    text: str


class ChatResult(BaseModel):
    status: Literal["ok", "refused", "insufficient"]
    answer: str
    matching_reviews: List[EvidenceReview]
    confidence: float = Field(ge=0, le=1)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(min_length=10, max_length=2_048)

    @field_validator("source_url")
    @classmethod
    def strip_source_url(cls, value: str) -> str:
        return value.strip()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(min_length=1, max_length=512)
    question: str = Field(min_length=1, max_length=1_000)

    @field_validator("source_key", "question")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value


@dataclass(frozen=True)
class ProviderDataset:
    source: Source
    reviews: List[Review]
    skipped_review_count: int
    warnings: List[str]
