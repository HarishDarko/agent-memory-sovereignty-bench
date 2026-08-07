"""Contamination preflight suite (isolation gate before any scored run)."""

from contamination.models import PreflightContext, PreflightResult
from contamination.preflight import run_preflight

__all__ = ["PreflightContext", "PreflightResult", "run_preflight"]
