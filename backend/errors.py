from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ConfigurationError(AppError):
    def __init__(self, variable: str) -> None:
        super().__init__(
            "PROVIDER_NOT_CONFIGURED",
            f"Server configuration is missing {variable}.",
            503,
        )


class InvalidSourceError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_SOURCE_URL", message, 400)


class DatasetUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "DATASET_UNAVAILABLE",
            "The review dataset is missing or expired. Ingest the source again.",
            404,
        )


class ProviderError(AppError):
    pass
