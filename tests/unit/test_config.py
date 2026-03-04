"""Tests for Config."""


from universal_extractor.config import Config


class TestConfig:
    def test_defaults(self):
        cfg = Config()
        assert cfg.whisper_model == "base"
        assert cfg.enable_whisper is True
        assert cfg.web_timeout == 30
        assert cfg.max_workers == 4

    def test_constructor_override(self):
        cfg = Config(whisper_model="medium", web_timeout=60)
        assert cfg.whisper_model == "medium"
        assert cfg.web_timeout == 60

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("UNIEXTRACT_WHISPER_MODEL", "small")
        monkeypatch.setenv("UNIEXTRACT_ENABLE_WHISPER", "false")
        monkeypatch.setenv("UNIEXTRACT_WEB_TIMEOUT", "10")
        monkeypatch.setenv("UNIEXTRACT_YOUTUBE_LANGUAGES", "de,fr")
        cfg = Config.from_env()
        assert cfg.whisper_model == "small"
        assert cfg.enable_whisper is False
        assert cfg.web_timeout == 10
        assert cfg.youtube_languages == ["de", "fr"]

    def test_from_env_overrides_take_priority(self, monkeypatch):
        monkeypatch.setenv("UNIEXTRACT_WHISPER_MODEL", "small")
        cfg = Config.from_env(whisper_model="large")
        assert cfg.whisper_model == "large"

    def test_validate_valid(self):
        cfg = Config()
        assert cfg.validate() == []

    def test_validate_bad_model(self):
        cfg = Config(whisper_model="huge")
        errors = cfg.validate()
        assert len(errors) == 1
        assert "huge" in errors[0]

    def test_validate_bad_timeout(self):
        cfg = Config(web_timeout=0)
        errors = cfg.validate()
        assert any("web_timeout" in e for e in errors)
