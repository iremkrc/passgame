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


@pytest.mark.parametrize("launcher", ["run-cluster.sh"])
@pytest.mark.parametrize("late_completion", [True, False])
@pytest.mark.parametrize("new_run",[False,True])
def test_empty_queue_rechecks_completion_before_reporting_failure(tmp_path, launcher, late_completion, new_run):
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
    archive = output/"cluster-source.tar.gz"
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
        "dataset_version":3, "initialization_policy":"neutral_seed",
        "tracks":["seeded"],
        "snapshot_commit": "fixture", "result_directory": "fixture-reminders",
    }
    (output/"cluster-snapshot.json").write_text(json.dumps(metadata))
    (output/"cluster-last-run.json").write_text(json.dumps({
        "snapshot_commit": "fixture", "job_id": "12345",
        "run_dir": "/cluster/workspace/passgame/runs/predefined-stop-fixture",
    }))
    if new_run:
        (output/"cluster-last-run.json").unlink()
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
if command.startswith("if [ -f ") or command.startswith("mkdir -p "):
    sys.exit(0)
if command.startswith("cd "):
    body = sys.stdin.read()
    assert "bash -s -- 'fixture-account' 'fixture-gpu' 'gpu:a100:1'" in command
    assert '--account="$1" --partition="$2"' in body
    assert '--gres="$3"' in body
    assert "'8' '96G' '24:00:00'" in command
    assert '--cpus-per-task="$4" --mem="$5" --time="$6"' in body
    (root/"submission").write_text("checked")
    print("12345")
    sys.exit(0)
raise SystemExit("Unexpected SSH command: "+command)
''')
    scp = binaries/"scp"
    scp.write_text('''#!/usr/bin/env python3
import json, sys
from pathlib import Path
source, destination = sys.argv[-2], Path(sys.argv[-1])
if source.endswith("cluster-source.tar.gz"):
    assert sys.argv[-1].startswith("fixture-cluster:")
    sys.exit(0)
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
           "PASSGAME_MOCK_DIR":str(tmp_path), "PASSGAME_LATE_COMPLETION":"1" if late_completion else "0",
           "PASSGAME_SSH_HOST":"fixture-cluster", "PASSGAME_REMOTE_ROOT":"/cluster/workspace/passgame",
           "PASSGAME_ACCOUNT":"fixture-account", "PASSGAME_PARTITION":"fixture-gpu",
           "PASSGAME_GPU_RESOURCE":"gpu:a100:1",
           "PASSGAME_CPUS_PER_TASK":"8", "PASSGAME_MEMORY":"96G", "PASSGAME_TIME_LIMIT":"24:00:00",
           "PASSGAME_CLUSTER_CONFIG":str(tmp_path/"absent-private-config.env")}
    result = subprocess.run(["bash", str(tmp_path/launcher),*(["--new"] if new_run else [])], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    assert (tmp_path/"completion-probes").read_text() == "2"
    assert (tmp_path/"submission").exists() == new_run
    report = output/"pilot-results-12345/fixture-reminders/completion.json"
    if late_completion:
        assert result.returncode == 0, result.stdout+result.stderr
        assert json.loads(report.read_text())["complete"] is True
        assert "ended without a completion report" not in result.stdout
    else:
        assert result.returncode == 1, result.stdout+result.stderr
        assert "ended without a completion report" in result.stdout
        assert not report.exists()


def test_cluster_serving_helper_runs_evaluator_and_stops_server(tmp_path):
    """Run the actual shell helper with a simulated GPU/container runtime."""
    source = Path(__file__).resolve().parents[1]
    directory = tmp_path/"scripts/cluster"
    directory.mkdir(parents=True)
    shutil.copy2(source/"scripts/cluster/serve_and_eval.sh", directory/"serve_and_eval.sh")
    binaries = tmp_path/"bin"
    binaries.mkdir()
    programs = {
        "nvidia-smi": '''#!/bin/bash
case "$*" in
  *--query-gpu=driver_version*) echo 580.0 ;;
  *-L*) echo 'GPU 0: test GPU' ;;
  *) echo 'CUDA Version: 13.0' ;;
esac
''',
        "apptainer": '''#!/bin/bash
printf '%s\\n' "$*" >> "$TEST_CALLS"
if [[ "$*" == *"vllm serve"* ]]; then
  echo $$ > "$TEST_SERVER_PID"
  exec sleep 30
fi
''',
        "curl": '#!/bin/bash\nexit 0\n',
        "git": '#!/bin/bash\necho fixture-commit\n',
        "uv": '#!/bin/bash\nprintf "%s\\n" "$*" >> "$TEST_CALLS"\n',
    }
    for name, content in programs.items():
        executable = binaries/name
        executable.write_text(content)
        executable.chmod(0o755)
    calls, server_pid = tmp_path/"calls", tmp_path/"server.pid"
    env = {**os.environ, "PATH": str(binaries)+os.pathsep+os.environ["PATH"],
           "SIF": str(tmp_path/"runtime.sif"), "MODEL_DIR": str(tmp_path/"weights"),
           "SERVED_NAME": "served-model", "CONFIG": "configs/cluster/model.yaml",
           "LOG_DIR": str(tmp_path/"logs"), "VLLM_CACHE_ROOT": str(tmp_path/"cache"),
           "TEST_CALLS": str(calls), "TEST_SERVER_PID": str(server_pid)}
    result = subprocess.run(["bash", str(directory/"serve_and_eval.sh")], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout+result.stderr
    recorded = calls.read_text()
    assert "--served-model-name served-model" in recorded
    assert "run --locked python -m passgame.run --config configs/cluster/model.yaml" in recorded
    # The server must be terminated even when evaluation completes immediately.
    if server_pid.exists():
        with pytest.raises(ProcessLookupError):
            os.kill(int(server_pid.read_text()), 0)
