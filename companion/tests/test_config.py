from wowwrapped.config import load_config, share_auto, writer_model, writer_voice


def test_defaults_without_a_file(tmp_path):
    cfg = load_config(tmp_path)
    assert not cfg.exists and cfg.error is None and cfg.warnings == ()
    assert cfg.share.auto is False and cfg.wrapped.voice is None


def test_unknown_keys_and_bad_values_warn_and_fall_back(tmp_path):
    (tmp_path / "wowwrapped.local.toml").write_text(
        '[share]\nauto = "yes"\nauot = true\n[sharing]\nauto = true\n[wrapped]\nvoice = "field-journal"\n'
        '[people."Moonhoof"]\nnote = "guildmate"\n[people."Nobody"]\n')
    cfg = load_config(tmp_path)
    assert cfg.share.auto is False
    assert cfg.wrapped.voice == "field-journal" and cfg.people == {"Moonhoof": "guildmate"}
    text = " | ".join(cfg.warnings)
    assert "[share] auto" in text and "[share] auot" in text and "[sharing]" in text and "Nobody" in text


def test_a_broken_file_is_an_error_and_everything_is_off(tmp_path):
    (tmp_path / "wowwrapped.local.toml").write_text("[share]\nauto = true\n[wrapped\nvoice = 1\n")
    cfg = load_config(tmp_path)
    assert cfg.error and "not valid TOML" in cfg.error
    assert share_auto(tmp_path) is False


def test_voice_and_model_precedence(tmp_path, monkeypatch):
    (tmp_path / "wowwrapped.local.toml").write_text('[wrapped]\nvoice = "field-journal"\nmodel = "opus"\n')
    assert writer_voice(None, tmp_path) == "field-journal" and writer_model(None, tmp_path) == "opus"
    monkeypatch.setenv("WOWWRAPPED_VOICE", "golden")
    assert writer_voice(None, tmp_path) == "golden"
    assert writer_voice("mine.md", tmp_path) == "mine.md" and writer_model("haiku", tmp_path) == "haiku"
    assert writer_voice(None, tmp_path / "elsewhere") == "golden" and writer_model(None, tmp_path / "elsewhere") is None
