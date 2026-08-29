"""Phase 17 生成产物兼容保护。"""

import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from src.cli import ENVIRONMENT_VARIABLES, SUPPORTED_FLAGS
from src.publication import build_catalog_signature, compare_catalogs
from scripts.validate_catalog_schema import validate_catalog


FIXTURE = Path("tests/fixtures/phase17_catalog_snapshot.json")


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_representative_snapshot_covers_critical_semantics():
    models = load_fixture()["models"]
    assert {model["price_status"] for model in models} == {
        "priced", "free", "free_tier", "non_token", "unknown", "unavailable", "retiring"
    }
    assert {model["model_source"] for model in models} == {"api", "fallback", "scrape"}
    assert {model["context_status"] for model in models} >= {
        "known", "inferred", "not_applicable", "unknown"
    }


def test_catalog_signature_ignores_order_and_collection_time():
    before = load_fixture()
    after = deepcopy(before)
    after["models"].reverse()
    for model in after["models"]:
        model["collected_at"] = "2099-01-01T00:00:00+00:00"
    assert build_catalog_signature(before) == build_catalog_signature(after)
    assert compare_catalogs(before, after)["compatible"] is True


def test_catalog_diff_reports_semantic_price_change():
    before = load_fixture()
    after = deepcopy(before)
    after["models"][0]["output_price"] = 99.0
    report = compare_catalogs(before, after)
    assert report["compatible"] is False
    assert report["changes"]["changed_count"] == 1
    assert report["changes"]["changed"][0]["fields"] == ["output_price"]


def test_generate_cli_and_environment_contract_matches_production_entry():
    tree = ast.parse(Path("generate.py").read_text(encoding="utf-8"))
    env_names = set()
    flags = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "os"
                and node.func.value.attr == "environ"
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                env_names.add(node.args[0].value)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant):
            if isinstance(node.left.value, str) and node.left.value.startswith("--"):
                flags.add(node.left.value)
    assert flags == set(SUPPORTED_FLAGS)
    assert env_names == set(ENVIRONMENT_VARIABLES)


def test_conflicting_render_only_flags_remain_rejected():
    result = subprocess.run(
        [sys.executable, "generate.py", "--render-only", "--refresh"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "--render-only 不能与 --refresh 或 --update-db 同时使用" in result.stderr


def test_committed_catalog_matches_phase17_compatibility_schema():
    validate_catalog(Path("models_data.json"))
