"""Compatibility façade for the opt-in data source adapters.

The implementation lives in :mod:`finpilot.data_sources`; this module keeps a
short provider import path for callers without changing the existing APIs.
"""
from .data_sources import (
    ProviderDependencyError,
    ProviderError,
    ProviderNetworkError,
    ProviderPolicyError,
    ProviderResult,
    ProviderValidationError,
    SecEdgarProvider,
    SourcePolicy,
    UserSnapshotProvider,
    YFinanceProvider,
    data_doctor,
    dependency_status,
)

__all__ = [
    "ProviderError",
    "ProviderPolicyError",
    "ProviderDependencyError",
    "ProviderNetworkError",
    "ProviderValidationError",
    "ProviderResult",
    "SourcePolicy",
    "UserSnapshotProvider",
    "YFinanceProvider",
    "SecEdgarProvider",
    "data_doctor",
    "dependency_status",
]
