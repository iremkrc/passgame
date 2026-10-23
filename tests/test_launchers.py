"""Exercise Galvani monitoring without SSH, a scheduler, or saved local artifacts."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest


@pytest.mark.parametrize("launcher", ["run-pilot.sh", "pilot.command"])
@pytest.mark.parametrize("late_completion", [True, False])
def test_empty_queue_rechecks_completion_before_reporting_failure(tmp_path, launcher, late_completion):
    root = Path(__file__).resolve().parents[1]
    shutil.copy2(root/launcher, tmp_path/launcher)
    (tmp_path/"src/passgame").mkdir(parents=True)
    (tmp_path/"configs").mkdir()
    output = tmp_path/"outputs"
    output.mkdir()
    code_hash = hashlib.sha256()
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path/name).write_bytes(b"")
        code_hash.update(name.encode())
    config = b"fixture configuration\n"
    (tmp_path/"configs/main.yaml").write_bytes(config)
    archive = output/"pilot-stop-on-failure.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("passgame/configs/experiment.yaml")
        member.size = len(config)
        bundle.addfile(member, io.BytesIO(config))
    metadata = {
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "code_hash": code_hash.hexdigest(), "config_path": "configs/main.yaml",
        "termination_policy": "first_failure",
        "state_policy": "initialize_once_then_successful_model_outputs",
        "rule_count": 8, "remind_previous_rules": True,
        "prompt_protocol_version": "cumulative_rule_reminders_v1",
        "snapshot_commit": "fixture", "result_directory": "fixture-reminders",
    }
    (output/"pilot-stop-on-failure-snapshot.json").write_text(json.dumps(metadata))
    (output/"pilot-last-run.json").write_text(json.dumps({
        "snapshot_commit": "fixture", "job_id": "12345",
        "run_dir": "/mnt/lustre/work/eickhoff/esx797/passgame/runs/predefined-stop-fixture",
    }))
    binaries = tmp_path/"bin"
    binaries.mkdir()
    ssh = binaries/"ssh"
    ssh.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
root = Path(os.environ["PASSGAME_MOCK_DIR"])
if "-O" in sys.argv:
    sys.exit(0)
command = sys.argv[-1]
if command.startswith("test -f "):
    counter = root/"completion-probes"
    count = int(counter.read_text())+1 if counter.exists() else 1
    counter.write_text(str(count))
    sys.exit(0 if count > 1 and os.environ["PASSGAME_LATE_COMPLETION"] == "1" else 1)
if command.startswith("squeue "):
    sys.exit(0)
if command.startswith("sacct "):
    print("12345 FAILED 1:0")
    sys.exit(0)
raise SystemExit("Unexpected SSH command: "+command)
''')
    scp = binaries/"scp"
    scp.write_text('''#!/usr/bin/env python3
import json, sys
from pathlib import Path
source, destination = sys.argv[-2], Path(sys.argv[-1])
if source.endswith(".log"):
    (destination/"evaluate-12345.log").write_text("completed\\n")
else:
    report = destination/"fixture-reminders"
    report.mkdir(parents=True)
    (report/"completion.json").write_text(json.dumps({"complete":True}))
    (report/"summary.csv").write_text("model,success\\nfixture,1\\n")
''')
    ssh.chmod(0o755)
    scp.chmod(0o755)
    env = {**os.environ, "PATH":str(binaries)+os.pathsep+os.environ["PATH"],
           "PASSGAME_MOCK_DIR":str(tmp_path), "PASSGAME_LATE_COMPLETION":"1" if late_completion else "0"}
    result = subprocess.run(["bash", str(tmp_path/launcher)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    assert (tmp_path/"completion-probes").read_text() == "2"
    report = output/"pilot-results-12345/fixture-reminders/completion.json"
    if late_completion:
        assert result.returncode == 0, result.stdout+result.stderr
        assert json.loads(report.read_text())["complete"] is True
        assert "ended without a completion report" not in result.stdout
    else:
        assert result.returncode == 1, result.stdout+result.stderr
        assert "ended without a completion report" in result.stdout
        assert not report.exists()
