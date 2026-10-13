"""Unit tests for paths and resource resolution module."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile

import pytest

# Ensure src/ is on sys.path for direct pytest execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.paths import (
    app_dir,
    data_dir,
    find_config,
    is_frozen,
    resource_path,
)


def test_is_frozen_default() -> None:
    """Test is_frozen() returns False in standard development python environment."""
    assert is_frozen() is False


def test_is_frozen_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_frozen() returns True when sys.frozen is simulated."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert is_frozen() is True


def test_app_dir_dev() -> None:
    """Test app_dir() returns project root when running in source dev mode."""
    root = app_dir()
    assert (root / "src" / "screen_translator").is_dir()


def test_app_dir_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test app_dir() returns executable directory when frozen."""
    fake_exe = tmp_path / "bin" / "ScreenTranslator.exe"
    fake_exe.parent.mkdir(parents=True, exist_ok=True)
    fake_exe.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert app_dir() == fake_exe.parent


def test_resource_path_dev() -> None:
    """Test resource_path() resolves relative to app_dir in dev mode."""
    res = resource_path("config.yaml")
    assert res == app_dir() / "config.yaml"


def test_resource_path_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test resource_path() resolves relative to sys._MEIPASS when frozen."""
    meipass = tmp_path / "_internal"
    meipass.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    res = resource_path("config.yaml")
    assert res == meipass / "config.yaml"


def test_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test data_dir() resolves to %APPDATA%/ScreenTranslator."""
    fake_appdata = tmp_path / "Roaming"
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    d = data_dir()
    assert d == fake_appdata / "ScreenTranslator"
    assert d.is_dir()


def test_find_config_cli_explicit(tmp_path: Path) -> None:
    """Test find_config with an explicit valid --config path."""
    custom_cfg = tmp_path / "custom.yaml"
    custom_cfg.write_text("capture:\n  fps: 10\n", encoding="utf-8")

    resolved = find_config(custom_cfg)
    assert resolved == custom_cfg.resolve()


def test_find_config_portable_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test find_config resolves to config.yaml next to app_dir() if present."""
    fake_root = tmp_path / "portable_app"
    fake_root.mkdir()
    portable_yaml = fake_root / "config.yaml"
    portable_yaml.write_text("capture:\n  fps: 5\n", encoding="utf-8")

    monkeypatch.setattr("screen_translator.paths.app_dir", lambda: fake_root)

    resolved = find_config()
    assert resolved == portable_yaml


def test_find_config_user_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test find_config resolves to data_dir()/config.yaml if portable config does not exist."""
    fake_root = tmp_path / "app_empty"
    fake_root.mkdir()

    fake_appdata = tmp_path / "AppData" / "ScreenTranslator"
    fake_appdata.mkdir(parents=True, exist_ok=True)
    user_yaml = fake_appdata / "config.yaml"
    user_yaml.write_text("capture:\n  fps: 3\n", encoding="utf-8")

    monkeypatch.setattr("screen_translator.paths.app_dir", lambda: fake_root)
    monkeypatch.setattr("screen_translator.paths.data_dir", lambda: fake_appdata)

    resolved = find_config()
    assert resolved == user_yaml


def test_find_config_first_run_copy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test find_config automatically copies bundled default config on first run."""
    fake_root = tmp_path / "app_first_run"
    fake_root.mkdir()

    bundled_file = tmp_path / "bundled" / "config.yaml"
    bundled_file.parent.mkdir(parents=True, exist_ok=True)
    bundled_file.write_text("capture:\n  fps: 2\n", encoding="utf-8")

    fake_appdata = tmp_path / "AppData" / "ScreenTranslator"
    # Notice user config does not exist yet

    monkeypatch.setattr("screen_translator.paths.app_dir", lambda: fake_root)
    monkeypatch.setattr("screen_translator.paths.data_dir", lambda: fake_appdata)
    monkeypatch.setattr("screen_translator.paths.resource_path", lambda rel: bundled_file)

    resolved = find_config()
    assert resolved == fake_appdata / "config.yaml"
    assert resolved.is_file()
    assert resolved.read_text(encoding="utf-8") == "capture:\n  fps: 2\n"
