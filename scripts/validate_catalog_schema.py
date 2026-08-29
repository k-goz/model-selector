#!/usr/bin/env python3
"""Validate a generated catalog against an explicit JSON Schema contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


DEFAULT_SCHEMA = Path("schemas/models-data.phase17-compat.schema.json")


def validate_catalog(data_path: Path, schema_path: Path = DEFAULT_SCHEMA) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        preview = "\n".join(
            f"- {'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors[:20]
        )
        raise ValueError(f"Schema validation failed ({len(errors)} errors):\n{preview}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", nargs="?", type=Path, default=Path("models_data.json"))
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    validate_catalog(args.data, args.schema)
    print(f"Schema validation passed: {args.data} <- {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
