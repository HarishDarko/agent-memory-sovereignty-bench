"""Preflight data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from benchmark.clock import BenchmarkClock
from benchmark.config import Settings
from benchmark.events import Event, GroundTruth, Query
from benchmark.providers import MemoryProvider

ProviderFactory = Callable[[Path], MemoryProvider]


@dataclass
class PreflightResult:
    check: str
    passed: bool
    required: bool = True
    applicable: bool = True
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "passed": self.passed,
            "required": self.required,
            "applicable": self.applicable,
            "details": self.details,
        }


@dataclass
class PreflightContext:
    provider_name: str
    provider_factory: ProviderFactory
    settings: Settings
    clock: BenchmarkClock
    events: list[Event] = field(default_factory=list)
    queries: list[Query] = field(default_factory=list)
    gold: dict[str, GroundTruth] = field(default_factory=dict)
    data_dir: Path | None = None
    is_control: bool = False  # True for no-memory/oracle controls (retrieve nothing)
    containerized: bool = False
    gateway: object | None = None  # live gateway for the semantic no-memory probe
