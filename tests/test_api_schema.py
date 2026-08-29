import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def test_api_v1_response_schema_accepts_current_catalog_page():
    catalog = json.loads((ROOT / "models_data.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/models-api.v1.schema.json").read_text(encoding="utf-8"))
    response = {
        "api_version": "1.0.0",
        "schema_version": catalog["meta"]["schema_version"],
        "data_updated_at": catalog["meta"]["updated_at"],
        "license": "Provider terms and source attribution apply.",
        "pagination": {"limit": 2, "returned": 2, "total": len(catalog["models"]), "next_cursor": "sample"},
        "items": catalog["models"][:2],
    }
    Draft202012Validator(schema).validate(response)
