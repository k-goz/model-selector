"""Runtime configuration loaded from environment and command-line flags."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
import os


API_KEY_ENV = {
    "siliconflow": "SF_KEY",
    "aliyun": "ALIYUN_KEY",
    "moonshot": "MS_KEY",
    "zhipu": "ZH_KEY",
    "volcengine": "VOLC_KEY",
    "tencent": "TENCENT_KEY",
    "spark": "SPARK_KEY",
    "minimax": "MINIMAX_KEY",
    "yi": "YI_KEY",
    "baichuan": "BAICHUAN_KEY",
    "jieyue": "JIEYUE_KEY",
    "deepseek": "DEEPSEEK_KEY",
    "baidu": "BAIDU_KEY",
    "groq": "GROQ_KEY",
    "together": "TOGETHER_KEY",
    "fireworks": "FIREWORKS_KEY",
    "cohere": "COHERE_KEY",
    "deepinfra": "DEEPINFRA_KEY",
    "aihubmix": "AIHUBMIX_KEY",
    "infini": "INFINI_KEY",
    "novita": "NOVITA_KEY",
    "n1n": "N1N_KEY",
    "ca": "CA_KEY",
}

RUNTIME_ENV = {
    "OUTPUT_FILE",
    "CACHE_DIR",
    "MODELS_JSON",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DEFER_SUCCESS_NOTIFICATION",
}


@dataclass(frozen=True)
class RuntimeConfig:
    project_dir: Path
    output_file: Path
    cache_dir: Path
    models_file: Path
    previous_data_file: Path
    api_keys: dict[str, str]
    telegram_bot_token: str
    telegram_chat_id: str
    defer_success_notification: bool
    update_db: bool
    force_refresh: bool
    render_only: bool

    @classmethod
    def from_environment(
        cls,
        script_file: str,
        argv: Sequence[str],
        environ: Mapping[str, str] | None = None,
    ) -> "RuntimeConfig":
        env = os.environ if environ is None else environ
        project_dir = Path(script_file).resolve().parent
        output_file = Path(env.get("OUTPUT_FILE", str(project_dir / "index.html")))
        cache_dir = Path(env.get("CACHE_DIR", str(project_dir / ".cache")))
        models_file = Path(env.get("MODELS_JSON", str(project_dir / "models_data.json")))
        update_db = "--update-db" in argv
        force_refresh = "--refresh" in argv
        render_only = "--render-only" in argv
        if render_only and (force_refresh or update_db):
            raise SystemExit("--render-only 不能与 --refresh 或 --update-db 同时使用")
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            project_dir=project_dir,
            output_file=output_file,
            cache_dir=cache_dir,
            models_file=models_file,
            previous_data_file=cache_dir / "prev_models.json",
            api_keys={platform: env.get(env_name, "") for platform, env_name in API_KEY_ENV.items()},
            telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=env.get("TELEGRAM_CHAT_ID", ""),
            defer_success_notification=env.get("DEFER_SUCCESS_NOTIFICATION") == "1",
            update_db=update_db,
            force_refresh=force_refresh,
            render_only=render_only,
        )

    def configured_api_keys(self) -> dict[str, bool]:
        return {platform: bool(value) for platform, value in self.api_keys.items()}
