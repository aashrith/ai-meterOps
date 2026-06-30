class MeteringError(Exception):
    """Base exception for application-level failures."""


class QuotaConfigurationMissing(MeteringError):
    pass


class QuotaExceeded(MeteringError):
    pass


class RequestAlreadyExists(MeteringError):
    pass


class RequestInProgress(MeteringError):
    pass


class GenerationFailed(MeteringError):
    pass


class MeteringStateInconsistent(MeteringError):
    """Raised when the persisted metering state is missing or contradictory."""
