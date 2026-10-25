"""Framework-free exception types shared by services and the API layer."""


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MediaError(AppError):
    status_code = 422
    code = "invalid_media"


class UnsupportedMediaType(MediaError):
    status_code = 415
    code = "unsupported_media_type"


class PayloadTooLarge(MediaError):
    status_code = 413
    code = "payload_too_large"


class ProviderUnavailable(AppError):
    """No provider configured (missing key / weights). Not a failure of the app."""
    status_code = 503
    code = "provider_unavailable"


class ProviderError(AppError):
    """Provider configured but the call failed (timeout, bad response, HTTP error)."""
    status_code = 502
    code = "provider_error"


class ClarificationNeeded(AppError):
    """A safety constraint cannot be satisfied; the user must adjust their input."""
    status_code = 422
    code = "clarification_needed"


class NotFound(AppError):
    status_code = 404
    code = "not_found"
