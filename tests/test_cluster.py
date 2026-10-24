"""Private settings are literal data and are not required in shared source."""

from pathlib import Path

import pytest

from passgame.cluster import required,settings


def test_local_settings_are_literal_and_override_environment(tmp_path,monkeypatch):
    monkeypatch.delenv("PASSGAME_CLUSTER_CONFIG",raising=False)
    monkeypatch.setenv("PASSGAME_REMOTE_ROOT","/cluster/environment")
    (tmp_path/"configs").mkdir()
    (tmp_path/"configs/cluster.local.env").write_text(
        '# Private local values\nPASSGAME_REMOTE_ROOT=/cluster/private\n'
        'PASSGAME_MODEL_DIR="/cluster/weights with spaces"\n'
        'PASSGAME_MODEL_PROVENANCE=\n'
        'PASSGAME_LITERAL="$(do-not-execute)"\n')
    values = settings(tmp_path)
    assert values["PASSGAME_REMOTE_ROOT"] == "/cluster/private"
    assert values["PASSGAME_MODEL_DIR"] == "/cluster/weights with spaces"
    assert values["PASSGAME_MODEL_PROVENANCE"] == ""
    assert values["PASSGAME_LITERAL"] == "$(do-not-execute)"


def test_missing_or_placeholder_setting_reports_the_key_without_a_path(tmp_path,monkeypatch):
    monkeypatch.setenv("PASSGAME_CLUSTER_CONFIG",str(tmp_path/"missing.env"))
    assert settings(tmp_path).get("PASSGAME_CLUSTER_CONFIG") == str(tmp_path/"missing.env")
    for value in ("","YOUR_WORKSPACE","/path/to/workspace"):
        with pytest.raises(ValueError,match="Set PASSGAME_REMOTE_ROOT") as error:
            required({"PASSGAME_REMOTE_ROOT":value},"PASSGAME_REMOTE_ROOT")
        assert str(tmp_path) not in str(error.value)


def test_invalid_local_assignment_does_not_echo_the_value(tmp_path,monkeypatch):
    path = tmp_path/"private.env"
    path.write_text('PASSGAME_MODEL_DIR=/private/unquoted model path\n')
    monkeypatch.setenv("PASSGAME_CLUSTER_CONFIG",str(path))
    with pytest.raises(ValueError,match="Quote values") as error:
        settings(tmp_path)
    assert "/private/" not in str(error.value)
