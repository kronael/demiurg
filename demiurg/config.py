from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    claude_api_key: str
    num_planners: int
    num_workers: int
    target_dir: str
    log_dir: str
    data_dir: str
    port: int

    @staticmethod
    def load() -> Config:
        """load config from env, ./.demiurg, ~/.demiurg/config"""
        home = Path.home()
        global_config = home / ".demiurg" / "config"
        local_config = Path(".demiurg")

        try:
            if global_config.exists():
                load_dotenv(global_config)

            if local_config.exists():
                load_dotenv(local_config, override=True)
        except Exception as e:
            raise RuntimeError(f"failed to load config files: {e}") from e

        api_key = os.getenv("CLAUDE_API_KEY", "")
        if not api_key:
            raise RuntimeError("CLAUDE_API_KEY not set")

        try:
            num_planners = int(os.getenv("NUM_PLANNERS", "2"))
            num_workers = int(os.getenv("NUM_WORKERS", "4"))
            port = int(os.getenv("PORT", "8080"))
        except ValueError as e:
            raise RuntimeError(f"invalid config value: {e}") from e

        return Config(
            claude_api_key=api_key,
            num_planners=num_planners,
            num_workers=num_workers,
            target_dir=os.getenv("TARGET_DIR", "."),
            log_dir=os.getenv("LOG_DIR", str(home / ".demiurg" / "log")),
            data_dir=os.getenv("DATA_DIR", str(home / ".demiurg" / "data")),
            port=port,
        )
