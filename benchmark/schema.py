"""Versioned schema contracts and a constrained, deterministic validation engine.

The JSON files under ``schemas/`` are the source of truth for every on-disk
record: events, queries, ground truth, run manifests, and result bundles.

This module implements a small deterministic subset of JSON Schema
(draft 2020-12 semantics) sufficient for those files: ``type`` (including
type lists such as ``["string", "null"]``), ``enum``, ``const``, ``required``,
``properties``, ``additionalProperties``, ``items``, ``pattern``,
``minLength``/``maxLength``, and ``minItems``. No ``$ref``, ``$defs``,
``allOf``, or remote references are used.

Migration policy: schemas are immutable once a benchmark version freezes. A
breaking change bumps the ``$id`` suffix (e.g. ``/1`` -> ``/2``) and the
manifest ``schema`` const. Old run artifacts remain readable under their own
schema id. If a later phase requires full JSON Schema, the engine here can be
replaced by the ``jsonschema`` package without touching the schema files.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
SCHEMA_VERSION = 1
ISO_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"


class SchemaError(ValueError):
    """Raised when a record or artifact violates its versioned schema."""


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / f"{name}.schema.json"
    if not path.exists():
        raise SchemaError(f"unknown schema: {name} (expected {path})")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _validate(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected_types = schema.get("type")
    if expected_types is not None:
        wanted = expected_types if isinstance(expected_types, list) else [expected_types]
        if not any(_matches_type(value, item) for item in wanted):
            errors.append(f"{path}: expected type {expected_types!r}, got {type(value).__name__}")
            return

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if isinstance(value, str):
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer items than minItems {schema['minItems']}")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(item, schema["items"], f"{path}[{index}]", errors)

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                _validate(value[key], child_schema, f"{path}.{key}", errors)
        if schema.get("additionalProperties") is False:
            unknown = [key for key in value if key not in properties]
            for key in sorted(unknown):
                errors.append(f"{path}: unexpected property {key!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']!r}")


def _validate_record(record: Any, schema_name: str) -> None:
    errors: list[str] = []
    _validate(record, load_schema(schema_name), "$", errors)
    if errors:
        raise SchemaError("; ".join(errors))


def validate_event_record(record: dict) -> None:
    _validate_record(record, "event")


def validate_query_record(record: dict) -> None:
    _validate_record(record, "query")


def validate_ground_truth_record(record: dict) -> None:
    _validate_record(record, "ground-truth")


def validate_manifest(manifest: dict) -> None:
    _validate_record(manifest, "manifest")
    status = manifest.get("status")
    if isinstance(status, str) and status.startswith("completed_") and manifest.get("scores") is None:
        raise SchemaError("$: completed run manifest must carry a scores object")


def validate_result_bundle(bundle: dict) -> None:
    _validate_record(bundle, "result-bundle")


def validate_provider_capabilities(record: dict) -> None:
    _validate_record(record, "provider-capabilities")
