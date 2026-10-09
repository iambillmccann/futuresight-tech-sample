from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable

from backend.models import Dataset, DatasetSummary, IngestResult, ProviderDataset


@dataclass
class CacheEntry:
    result: IngestResult


def build_summary(provider_dataset: ProviderDataset) -> DatasetSummary:
    reviews = provider_dataset.reviews
    distribution = {str(rating): 0 for rating in range(1, 6)}
    dated_reviews: list[str] = []
    for review in reviews:
        distribution[str(round(review.rating))] += 1
        if review.date:
            try:
                dated_reviews.append(
                    datetime.fromisoformat(review.date.replace("Z", "+00:00")).date().isoformat()
                )
            except ValueError:
                pass
    return DatasetSummary(
        review_count=len(reviews),
        average_rating=round(
            sum(review.rating for review in reviews) / len(reviews), 2
        ),
        rating_distribution=distribution,
        earliest_review=min(dated_reviews) if dated_reviews else None,
        latest_review=max(dated_reviews) if dated_reviews else None,
        skipped_review_count=provider_dataset.skipped_review_count,
        ingestion_status=(
            "partial"
            if provider_dataset.skipped_review_count or provider_dataset.warnings
            else "complete"
        ),
    )


class ReviewDatasetCache:
    def __init__(
        self,
        ttl_seconds: int,
        max_entries: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._aliases: dict[str, str] = {}
        self._inflight: dict[str, Future[IngestResult]] = {}
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._aliases.clear()
            self._inflight.clear()

    def get(self, source_key: str) -> IngestResult | None:
        with self._lock:
            return self._get_locked(source_key)

    def get_or_ingest(
        self,
        hint_key: str,
        ingest: Callable[[], ProviderDataset],
    ) -> IngestResult:
        with self._lock:
            cached = self._get_locked(hint_key)
            if cached:
                return cached.model_copy(update={"cache_hit": True})
            future = self._inflight.get(hint_key)
            leader = future is None
            if future is None:
                future = Future()
                self._inflight[hint_key] = future

        if not leader:
            result = future.result()
            return result.model_copy(update={"cache_hit": True})

        try:
            provider_dataset = ingest()
            now = self._clock()
            summary = build_summary(provider_dataset)
            result = IngestResult(
                source=provider_dataset.source,
                dataset=Dataset(
                    total_reviews=len(provider_dataset.reviews),
                    sample_reviews=provider_dataset.reviews,
                    summary=summary,
                ),
                cache_hit=False,
                fetched_at=now,
                expires_at=now + self._ttl,
                warnings=provider_dataset.warnings,
            )
            with self._lock:
                existing = self._get_locked(provider_dataset.source.source_key)
                if existing:
                    result = existing.model_copy(update={"cache_hit": True})
                else:
                    self._entries[provider_dataset.source.source_key] = CacheEntry(
                        result=result
                    )
                    self._entries.move_to_end(provider_dataset.source.source_key)
                    self._evict_locked()
                self._aliases[hint_key] = provider_dataset.source.source_key
            future.set_result(result)
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self._lock:
                self._inflight.pop(hint_key, None)

    def _get_locked(self, source_key: str) -> IngestResult | None:
        canonical_key = self._aliases.get(source_key, source_key)
        entry = self._entries.get(canonical_key)
        if not entry:
            return None
        if entry.result.expires_at <= self._clock():
            del self._entries[canonical_key]
            self._aliases = {
                alias: target
                for alias, target in self._aliases.items()
                if target != canonical_key
            }
            return None
        self._entries.move_to_end(canonical_key)
        return entry.result

    def _evict_locked(self) -> None:
        while len(self._entries) > self._max_entries:
            evicted_key, _ = self._entries.popitem(last=False)
            self._aliases = {
                alias: target
                for alias, target in self._aliases.items()
                if target != evicted_key
            }
