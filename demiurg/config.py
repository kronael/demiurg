from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    num_planners: int
    num_workers: int
    target_dir: str
    log_dir: str
    data_dir: str
    port: int

    @staticmethod
    def load() -> Config:
        """load config from .env file and environment variables"""
        # load from local .env if it exists (env vars override)
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)

        try:
            num_planners = int(os.getenv("NUM_PLANNERS", "2"))
            num_workers = int(os.getenv("NUM_WORKERS", "4"))
            port = int(os.getenv("PORT", "8080"))
        except ValueError as e:
            raise RuntimeError(f"invalid config value: {e}") from e

        # validate positive integers
        if num_planners < 1:
            raise RuntimeError(f"NUM_PLANNERS must be positive, got {num_planners}")
        if num_workers < 1:
            raise RuntimeError(f"NUM_WORKERS must be positive, got {num_workers}")
        if port < 1 or port > 65535:
            raise RuntimeError(f"PORT must be 1-65535, got {port}")

        target_dir = os.getenv("TARGET_DIR", ".")
        target_path = Path(target_dir)
        if not target_path.exists():
            raise RuntimeError(f"TARGET_DIR does not exist: {target_dir}")
        if not target_path.is_dir():
            raise RuntimeError(f"TARGET_DIR is not a directory: {target_dir}")

        return Config(
            num_planners=num_planners,
            num_workers=num_workers,
            target_dir=target_dir,
            log_dir=os.getenv("LOG_DIR", f"{target_dir}/.demiurg/log"),
            data_dir=os.getenv("DATA_DIR", f"{target_dir}/.demiurg"),
            port=port,
        )
