from pathlib import Path


def test_generate_is_a_thin_stable_cli_entrypoint():
    source = Path("generate.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 30
    assert "from src.pipeline import run" in source
    assert 'if __name__ == "__main__":' in source
    assert "collect_platform_catalog" not in source
    assert "models_data.json" not in source
