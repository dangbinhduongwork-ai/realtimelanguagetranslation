"""Configuration loading and validation for Screen Translator."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
from typing import Any

import yaml

from screen_translator.paths import find_config

logger = logging.getLogger(__name__)

HEX_COLOR_REGEX = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(ValueError):
    """Raised when configuration values are missing, invalid, or malformed."""


@dataclass(frozen=True)
class CaptureConfig:
    """Screen capture parameters."""

    fps: int = 2
    monitor: int = 1
    region: tuple[int, int, int, int] | None = None
    settle_ms: int = 300
    max_wait_ms: int = 1500


@dataclass(frozen=True)
class ChangeDetectionConfig:
    """Frame change detection parameters."""

    threshold: float = 0.02


@dataclass(frozen=True)
class OcrConfig:
    """OCR engine parameters."""

    engine: str = "rapidocr"
    min_confidence: float = 0.6
    merge_lines: bool = True
    max_gap_ratio: float = 0.8
    upscale: str | float = "auto"
    small_text_px: int = 14


@dataclass(frozen=True)
class TranslateConfig:
    """Translation provider parameters."""

    provider: str = "google"
    source_lang: str = "en"
    target_lang: str = "vi"
    cache_size: int = 2000


@dataclass(frozen=True)
class OverlayConfig:
    """Overlay visual parameters."""

    opacity: float = 0.9
    font_family: str = "Segoe UI"
    font_size: int = 14
    background_color: str = "#000000"
    text_color: str = "#FFFFFF"
    show_region_border: bool = True


@dataclass(frozen=True)
class HotkeysConfig:
    """Global keyboard shortcuts."""

    toggle: str = "<ctrl>+<alt>+t"
    select_region: str = "<ctrl>+<alt>+r"
    quit: str = "<ctrl>+<alt>+q"


@dataclass(frozen=True)
class LoggingConfig:
    """Application logging parameters."""

    level: str = "INFO"


@dataclass(frozen=True)
class AppConfig:
    """Root configuration holding all sub-configurations."""

    capture: CaptureConfig = field(default_factory=CaptureConfig)
    change_detection: ChangeDetectionConfig = field(default_factory=ChangeDetectionConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    translate: TranslateConfig = field(default_factory=TranslateConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _validate_config(config: AppConfig) -> None:
    """Validate all configuration attributes and raise ConfigError on violations."""
    c = config.capture
    if not isinstance(c.fps, int) or not (1 <= c.fps <= 60):
        raise ConfigError(f"capture.fps must be an integer between 1 and 60, got: {c.fps}")
    if not isinstance(c.monitor, int) or c.monitor < 1:
        raise ConfigError(f"capture.monitor must be an integer >= 1, got: {c.monitor}")
    if c.region is not None:
        if not (isinstance(c.region, (list, tuple)) and len(c.region) == 4):
            raise ConfigError("capture.region must be a 4-tuple [left, top, width, height] or null")
        if c.region[2] <= 0 or c.region[3] <= 0:
            raise ConfigError("capture.region width and height must be positive")
    if not isinstance(c.settle_ms, int) or c.settle_ms < 0:
        raise ConfigError(f"capture.settle_ms must be a non-negative integer, got: {c.settle_ms}")
    if not isinstance(c.max_wait_ms, int) or c.max_wait_ms < 0:
        raise ConfigError(f"capture.max_wait_ms must be a non-negative integer, got: {c.max_wait_ms}")

    cd = config.change_detection
    if not isinstance(cd.threshold, (int, float)) or not (0.0 <= cd.threshold <= 1.0):
        raise ConfigError(f"change_detection.threshold must be a float between 0.0 and 1.0, got: {cd.threshold}")

    o = config.ocr
    if o.engine not in {"rapidocr"}:
        raise ConfigError(f"Unsupported ocr.engine: '{o.engine}'. Supported: ['rapidocr']")
    if not isinstance(o.min_confidence, (int, float)) or not (0.0 <= o.min_confidence <= 1.0):
        raise ConfigError(f"ocr.min_confidence must be between 0.0 and 1.0, got: {o.min_confidence}")
    if not isinstance(o.merge_lines, bool):
        raise ConfigError(f"ocr.merge_lines must be a boolean, got: {o.merge_lines}")
    if not isinstance(o.max_gap_ratio, (int, float)) or o.max_gap_ratio < 0.0:
        raise ConfigError(f"ocr.max_gap_ratio must be a non-negative number, got: {o.max_gap_ratio}")

    valid_upscale = False
    if isinstance(o.upscale, str) and o.upscale.lower() == "auto":
        valid_upscale = True
    elif isinstance(o.upscale, (int, float)) and o.upscale >= 1.0:
        valid_upscale = True
    if not valid_upscale:
        raise ConfigError(f"ocr.upscale must be 'auto' or a number >= 1.0, got: {o.upscale}")

    if not isinstance(o.small_text_px, int) or o.small_text_px <= 0:
        raise ConfigError(f"ocr.small_text_px must be a positive integer, got: {o.small_text_px}")

    t = config.translate
    if t.provider not in {"google"}:
        raise ConfigError(f"Unsupported translate.provider: '{t.provider}'. Supported: ['google']")
    if not t.source_lang or not isinstance(t.source_lang, str):
        raise ConfigError("translate.source_lang must be a non-empty string")
    if not t.target_lang or not isinstance(t.target_lang, str):
        raise ConfigError("translate.target_lang must be a non-empty string")
    if not isinstance(t.cache_size, int) or t.cache_size < 0:
        raise ConfigError(f"translate.cache_size must be a non-negative integer, got: {t.cache_size}")

    ov = config.overlay
    if not isinstance(ov.opacity, (int, float)) or not (0.0 <= ov.opacity <= 1.0):
        raise ConfigError(f"overlay.opacity must be between 0.0 and 1.0, got: {ov.opacity}")
    if not ov.font_family or not isinstance(ov.font_family, str):
        raise ConfigError("overlay.font_family must be a non-empty string")
    if not isinstance(ov.font_size, int) or ov.font_size <= 0:
        raise ConfigError(f"overlay.font_size must be a positive integer, got: {ov.font_size}")
    if not HEX_COLOR_REGEX.match(ov.background_color):
        raise ConfigError(f"overlay.background_color must be hex format (#RRGGBB), got: '{ov.background_color}'")
    if not HEX_COLOR_REGEX.match(ov.text_color):
        raise ConfigError(f"overlay.text_color must be hex format (#RRGGBB), got: '{ov.text_color}'")
    if not isinstance(ov.show_region_border, bool):
        raise ConfigError(f"overlay.show_region_border must be a boolean, got: {ov.show_region_border}")

    hk = config.hotkeys
    for name, val in [("toggle", hk.toggle), ("select_region", hk.select_region), ("quit", hk.quit)]:
        if not val or not isinstance(val, str):
            raise ConfigError(f"hotkeys.{name} must be a non-empty key sequence string")

    log_lvl = config.logging.level.upper() if isinstance(config.logging.level, str) else ""
    if log_lvl not in VALID_LOG_LEVELS:
        raise ConfigError(f"logging.level must be one of {sorted(VALID_LOG_LEVELS)}, got: '{config.logging.level}'")


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load, parse, and validate application configuration from YAML.

    Args:
        path: Path to config.yaml. If None, searches standard locations.

    Returns:
        AppConfig: Validated application configuration.

    Raises:
        ConfigError: If the file cannot be read, YAML is invalid, or values fail validation.
    """
    if path is not None:
        target_path = Path(path)
        if not target_path.is_file():
            raise ConfigError(f"Configuration file not found: {target_path}")
    else:
        target_path = find_config()
        if not target_path.is_file():
            logger.info("No config.yaml found in default paths, using built-in defaults.")
            default_cfg = AppConfig()
            _validate_config(default_cfg)
            return default_cfg

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data: Any = yaml.safe_load(f) or {}
    except Exception as exc:
        raise ConfigError(f"Failed to parse YAML from {target_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(data).__name__}")

    cap_raw = data.get("capture", {}) or {}
    region_raw = cap_raw.get("region")
    region_tuple = tuple(region_raw) if isinstance(region_raw, (list, tuple)) else None

    app_config = AppConfig(
        capture=CaptureConfig(
            fps=cap_raw.get("fps", 2),
            monitor=cap_raw.get("monitor", 1),
            region=region_tuple,
            settle_ms=cap_raw.get("settle_ms", 300),
            max_wait_ms=cap_raw.get("max_wait_ms", 1500),
        ),
        change_detection=ChangeDetectionConfig(**(data.get("change_detection", {}) or {})),
        ocr=OcrConfig(**(data.get("ocr", {}) or {})),
        translate=TranslateConfig(**(data.get("translate", {}) or {})),
        overlay=OverlayConfig(**(data.get("overlay", {}) or {})),
        hotkeys=HotkeysConfig(**(data.get("hotkeys", {}) or {})),
        logging=LoggingConfig(level=str((data.get("logging", {}) or {}).get("level", "INFO")).upper()),
    )

    _validate_config(app_config)
    return app_config
