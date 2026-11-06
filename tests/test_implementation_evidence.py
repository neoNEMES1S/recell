import json

import pytest

from second_life_battery.utils.study import begin, complete, verified, write_json


def test_completed_study_rejects_changed_inputs_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "protocol.yaml"
    config.write_text("scope: fixture\n")
    out = tmp_path / "run"
    registration = begin(out, config)
    write_json(out / "result.json", {"score": 4.4})
    complete(out, registration, scope="software fixture")
    assert verified(out)["status"] == "completed"
    original = config.read_bytes()
    config.write_text("scope: changed\n")
    with pytest.raises(ValueError, match="input changed"):
        verified(out)
    config.write_bytes(original)
    (out / "result.json").write_text(json.dumps({"score": 0}))
    with pytest.raises(ValueError, match="artifact changed"):
        verified(out)
    with pytest.raises(FileExistsError):
        begin(out, config)


def test_incomplete_run_is_not_publishable(tmp_path):
    (tmp_path / "completion.json").write_text('{"status":"running"}')
    with pytest.raises(ValueError, match="not complete"):
        verified(tmp_path)
