"""Unit tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import pytest

# Ensure src/ is on sys.path for direct pytest execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.config import (  # noqa: E402
    AppConfig,
    ConfigError,
    load_config,
)


def test_default_config_loading() -> None:
    """Test loading configuration from existing config.yaml or fallback defaults."""
    config = load_config()
    assert isinstance(config, AppConfig)
    assert config.capture.fps == 2
    assert config.capture.monitor == 1
    assert config.change_detection.threshold == 0.02
    assert config.ocr.engine == "rapidocr"
    assert config.ocr.min_confidence == 0.6
    assert config.ocr.merge_lines is True
    assert config.translate.provider == "google"
    assert config.translate.source_lang == "en"
    assert config.translate.target_lang == "vi"
    assert config.translate.cache_size == 2000
    assert config.overlay.opacity == 0.9
    assert config.overlay.font_family == "Segoe UI"
    assert config.overlay.font_size == 14
    assert config.overlay.background_color == "#000000"
    assert config.overlay.text_color == "#FFFFFF"
    assert config.hotkeys.toggle == "<ctrl>+<alt>+t"
    assert config.logging.level == "INFO"


def test_custom_valid_config() -> None:
    """Test loading valid custom YAML config."""
    yaml_content = """
capture:
  fps: 5
  monitor: 2
  region: [100, 100, 800, 600]
change_detection:
  threshold: 0.05
ocr:
  engine: rapidocr
  min_confidence: 0.75
  merge_lines: false
translate:
  provider: google
  source_lang: en
  target_lang: vi
  cache_size: 500
overlay:
  opacity: 0.8
  font_family: "Arial"
  font_size: 16
  background_color: "#112233"
  text_color: "#EEFFEE"
hotkeys:
  toggle: "<ctrl>+<shift>+t"
  select_region: "<ctrl>+<shift>+r"
  quit: "<ctrl>+<shift>+q"
logging:
  level: DEBUG
"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert config.capture.fps == 5
        assert config.capture.monitor == 2
        assert config.capture.region == (100, 100, 800, 600)
        assert config.change_detection.threshold == 0.05
        assert config.ocr.min_confidence == 0.75
        assert config.ocr.merge_lines is False
        assert config.overlay.font_size == 16
        assert config.logging.level == "DEBUG"
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_invalid_fps_raises() -> None:
    """Test that out-of-range fps raises ConfigError."""
    yaml_content = "capture: {fps: 100}\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(ConfigError, match="capture.fps"):
            load_config(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_invalid_color_raises() -> None:
    """Test that invalid hex color string raises ConfigError."""
    yaml_content = "overlay: {background_color: 'invalid-color'}\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(ConfigError, match="overlay.background_color"):
            load_config(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_invalid_log_level_raises() -> None:
    """Test that unrecognized log level raises ConfigError."""
    yaml_content = "logging: {level: 'VERBOSE'}\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(ConfigError, match="logging.level"):
            load_config(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_nonexistent_file_raises() -> None:
    """Test that specifying a missing file path raises ConfigError."""
    with pytest.raises(ConfigError, match="Configuration file not found"):
        load_config("nonexistent_path_to_config.yaml")
