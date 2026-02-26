"""Tests for the Settings Service."""

import json

from src.services.settings_service import (
    AutoApprovalSettings,
    DEFAULT_AUTO_APPROVE_TOOLS,
    SettingsService,
)


class TestSettingsDefaults:
    def test_returns_defaults_when_no_file(self, tmp_path):
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        settings = svc.get()
        assert settings.auto_approve_enabled is True
        assert settings.auto_approve_tools == DEFAULT_AUTO_APPROVE_TOOLS

    def test_returns_defaults_when_file_corrupt(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("not json!", encoding="utf-8")
        svc = SettingsService(settings_path=path)
        settings = svc.get()
        assert settings.auto_approve_enabled is True

    def test_returns_defaults_when_file_empty(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{}", encoding="utf-8")
        svc = SettingsService(settings_path=path)
        settings = svc.get()
        assert settings.auto_approve_enabled is True
        assert settings.auto_approve_tools == DEFAULT_AUTO_APPROVE_TOOLS


class TestSettingsPersistence:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        svc.update(auto_approve_enabled=False, auto_approve_tools=["Bash"])

        # Reload from disk
        svc2 = SettingsService(settings_path=path)
        settings = svc2.get()
        assert settings.auto_approve_enabled is False
        assert settings.auto_approve_tools == ["Bash"]

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "settings.json"
        svc = SettingsService(settings_path=path)
        svc.update(auto_approve_enabled=True)
        assert path.exists()

    def test_file_format(self, tmp_path):
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        svc.update(auto_approve_enabled=True, auto_approve_tools=["Read", "Glob"])

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["auto_approve_enabled"] is True
        assert data["auto_approve_tools"] == ["Read", "Glob"]


class TestSettingsUpdate:
    def test_partial_update_enabled_only(self, tmp_path):
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        result = svc.update(auto_approve_enabled=False)
        assert result.auto_approve_enabled is False
        assert result.auto_approve_tools == DEFAULT_AUTO_APPROVE_TOOLS

    def test_partial_update_tools_only(self, tmp_path):
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        result = svc.update(auto_approve_tools=["Bash", "Write"])
        assert result.auto_approve_enabled is True
        assert result.auto_approve_tools == ["Bash", "Write"]

    def test_full_update(self, tmp_path):
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        result = svc.update(
            auto_approve_enabled=False,
            auto_approve_tools=["Edit"],
        )
        assert result.auto_approve_enabled is False
        assert result.auto_approve_tools == ["Edit"]

    def test_update_returns_copy(self, tmp_path):
        """Modifying returned settings should not affect internal state."""
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        result = svc.update(auto_approve_tools=["Read"])
        result.auto_approve_tools.append("INJECTED")
        # Internal state should be unmodified
        assert "INJECTED" not in svc.get().auto_approve_tools

    def test_get_returns_copy(self, tmp_path):
        """Modifying returned settings should not affect internal state."""
        path = tmp_path / "settings.json"
        svc = SettingsService(settings_path=path)
        settings = svc.get()
        settings.auto_approve_tools.append("INJECTED")
        assert "INJECTED" not in svc.get().auto_approve_tools


class TestSettingsLoadFromExisting:
    def test_loads_existing_file(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({
                "auto_approve_enabled": False,
                "auto_approve_tools": ["Bash", "Write"],
            }),
            encoding="utf-8",
        )
        svc = SettingsService(settings_path=path)
        settings = svc.get()
        assert settings.auto_approve_enabled is False
        assert settings.auto_approve_tools == ["Bash", "Write"]
