"""Application directory and path resolution utilities."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import sys

logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller frozen bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") or getattr(sys, "frozen", False)


def app_dir() -> Path:
    """Return application root directory (exe folder when frozen, project root in dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # src/screen_translator/paths.py -> root is 3 levels up
    return Path(__file__).resolve().parent.parent.parent


def resource_path(relative_path: str | Path) -> Path:
    """Return absolute path to a bundled resource file."""
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", app_dir()))
    else:
        base = app_dir()
    return base / relative_path


def data_dir() -> Path:
    """Return persistent user application data directory (%APPDATA%/ScreenTranslator)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        target = Path(appdata) / "ScreenTranslator"
    else:
        target = Path.home() / ".config" / "ScreenTranslator"

    target.mkdir(parents=True, exist_ok=True)
    return target


def find_config(cli_config: str | Path | None = None) -> Path:
    """Resolve config.yaml using standard precedence order.

    Precedence:
    1. Explicit `--config PATH` argument if specified.
    2. Portable mode: `config.yaml` located next to the executable / app root.
    3. User profile: `%APPDATA%/ScreenTranslator/config.yaml`.
       If missing on first run, copies bundled default `config.yaml` there.

    Args:
        cli_config: Optional CLI configuration override.

    Returns:
        Path: Resolved configuration file path.
    """
    # 1. Explicit CLI option
    if cli_config:
        cli_path = Path(cli_config).resolve()
        if cli_path.is_file():
            return cli_path
        logger.warning("CLI config path %s does not exist; checking standard paths", cli_path)

    # 2. Portable mode: config.yaml next to executable / app root
    portable_config = app_dir() / "config.yaml"
    if portable_config.is_file():
        return portable_config

    # 3. User data directory: %APPDATA%/ScreenTranslator/config.yaml
    user_config = data_dir() / "config.yaml"
    if user_config.is_file():
        return user_config

    # First-run initialization: copy bundled default config.yaml to data_dir()
    bundled_default = resource_path("config.yaml")
    if bundled_default.is_file():
        try:
            user_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_default, user_config)
            logger.info("Initialized default configuration at %s", user_config)
            return user_config
        except Exception as exc:
            logger.warning("Could not copy default config to %s: %s", user_config, exc)
            return bundled_default

    return user_config
