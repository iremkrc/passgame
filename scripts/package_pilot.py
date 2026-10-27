"""Build the Galvani pilot archive from source; no ignored prior archive is needed.

Run from a checkout: uv run --locked python scripts/package_pilot.py
For another model, pass a matching --config, --model-dir and --model-revision.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import uuid

import yaml

from passgame.cluster import required, settings
from passgame.sequential import FAMILIES

QWEN_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"


def package(root: Path, config_path: Path, model_dir: str | None = None, model_revision: str | None = None) -> dict:
    root = root.resolve()
    config_path = (root/config_path).resolve()
    relative_config = config_path.relative_to(root)
    config = yaml.safe_load(config_path.read_text())
    if (config.get("tracks") not in (["seeded"],["order"]) or config.get("rule_count") != 8
            or config.get("remind_previous_rules") is not True or len(config["models"]) != 1):
        raise ValueError("Package one eight-rule seeded or order model with previous-rule reminders")
    data_path = Path(config["dataset_dir"])
    if data_path.is_absolute() or ".." in data_path.parts or data_path.parts[0] != "data":
        raise ValueError("The packaged dataset must be under the checkout's data directory")
    result = Path(config["output_dir"])
    if result.parent != Path("outputs") or not all(c.isalnum() or c in "_.-" for c in result.name):
        raise ValueError("Use a unique outputs/<simple-name> result directory")
    model = config["models"][0]
    endpoint = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})/v1", str(model.get("base_url", "")))
    if model.get("deployment") != "self_hosted" or endpoint is None or not 1 <= int(endpoint[1]) <= 65535:
        raise ValueError("The Galvani wrapper requires a self-hosted http://127.0.0.1:<port>/v1 endpoint")
    port = int(endpoint[1])
    if model_dir is None:
        if model["model_id"] != "qwen2.5-7b-instruct":
            raise ValueError("A new model needs --model-dir and --model-revision; renaming Qwen does not change its weights")
    elif not model_revision:
        raise ValueError("Record --model-revision when selecting different weights")
    private = settings(root)
    work = required(private,"PASSGAME_REMOTE_ROOT")
    if not Path(work).is_absolute():
        raise ValueError("PASSGAME_REMOTE_ROOT must be an absolute remote workspace")
    if model_dir is None:
        model_dir = required(private,"PASSGAME_MODEL_DIR")
        model_revision = model_revision or private.get("PASSGAME_MODEL_REVISION") or QWEN_REVISION
    if not Path(model_dir).is_absolute():
        raise ValueError("--model-dir must be an absolute path on Galvani")
    run_id = "progressive-v3-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:6]
    launch = root/"outputs/launches"/run_id
    snapshot = launch/"passgame"
    snapshot.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__","*.pyc",".pytest_cache",".DS_Store","local","*.local.env","pilot-runtime.env")
    for name in ("src","tests","docs","configs","data","scripts"):
        shutil.copytree(root/name,snapshot/name,ignore=ignore)
    for name in ("README.md","pyproject.toml","uv.lock",".gitignore",".python-version","run-pilot.sh","pilot.command"):
        shutil.copy2(root/name,snapshot/name)
    shutil.copy2(config_path,snapshot/"configs/experiment.yaml")
    runtime = {"WORK":work,"SIF":required(private,"PASSGAME_SIF"),"MODEL_DIR":model_dir,
               "SERVED_NAME":model["model_id"],"MODEL_REVISION":model_revision,
               "PORT":str(port),
               "MAX_MODEL_LEN":str(model["max_input_tokens"]),
               "MODEL_PROVENANCE":private.get("PASSGAME_MODEL_PROVENANCE","")}
    (snapshot/"configs/pilot-runtime.env").write_text("".join(k+"="+shlex.quote(v)+"\n" for k,v in runtime.items()))
    for args in (("init","-q"),("config","user.name","PassGame Snapshot"),
                 ("config","user.email","passgame-snapshot@localhost"),("add","."),
                 ("commit","-qm","Freeze progressive v3 pilot")):
        subprocess.run(["git",*args],cwd=snapshot,check=True,capture_output=True,text=True)
    commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=snapshot,text=True).strip()
    preflight = subprocess.run(["uv","run","--locked","python","-m","passgame.run", "--config","configs/experiment.yaml","--preflight"],
                               cwd=snapshot,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (launch/"preflight.log").write_text(preflight.stdout)
    if preflight.returncode:
        raise ValueError(f"Snapshot preflight failed; inspect {launch.relative_to(root)/'preflight.log'}")
    plan = json.loads(next(line[7:] for line in preflight.stdout.splitlines() if line.startswith("CONFIG ")))
    if plan.get("dataset_version") != 3 or plan.get("episode_suite") != "progressive_seeded_v1":
        raise ValueError("Package requires the version-3 progressive dataset")
    if subprocess.check_output(["git","status","--porcelain"],cwd=snapshot,text=True):
        raise ValueError("Frozen snapshot changed during preflight")
    archive = launch/"source.tar.gz"
    def archive_filter(info):
        return None if any(p in {".venv","__pycache__",".pytest_cache"} for p in Path(info.name).parts) or info.name.endswith(".pyc") else info
    with tarfile.open(archive,"w:gz") as bundle:
        bundle.add(snapshot,arcname="passgame",filter=archive_filter)
    metadata = {"run_id":run_id,"snapshot_commit":commit,
                **{k:plan[k] for k in ("code_hash","config_hash","dataset_hash","dataset_version","episode_suite")},
                "config_path":str(relative_config),"dataset_dir":str(data_path),"result_directory":result.name,
                "rule_count":8,"tracks":config["tracks"],
                "selection_version":"progressive_eight_rule_v1","initialization_policy":"neutral_seed",
                "termination_policy":"first_failure","state_policy":"initialize_once_then_successful_model_outputs",
                "remind_previous_rules":True,"prompt_protocol_version":"cumulative_rule_reminders_v1",
                "protocol_version":"neutral_seed_model_outputs_stop_on_failure_v1",
                "maximum_requests":plan["planned_records"],"planned_episodes":plan["planned_episodes"],
                "families":list(FAMILIES),
                "model":model["model_id"],"model_revision":model_revision,"model_dir":model_dir,
                "endpoint":model["base_url"],"port":port,
                "response_protocol":plan["response_protocol"],"generation_parameters":model["parameters"],
                "serving_image":"vllm/vllm-openai:v0.24.0",
                "archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}
    (launch/"snapshot.json").write_text(json.dumps(metadata,indent=2)+"\n")
    target = root/"outputs/pilot-stop-on-failure.tar.gz"
    shutil.copy2(archive,target.with_suffix(".tmp"))
    target.with_suffix(".tmp").replace(target)
    target = root/"outputs/pilot-stop-on-failure-snapshot.json"
    target.with_suffix(".tmp").write_text(json.dumps(metadata,indent=2)+"\n")
    target.with_suffix(".tmp").replace(target)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",type=Path,default=Path("configs/dev-qwen2.5-7b-eight-rules.yaml"))
    parser.add_argument("--model-dir")
    parser.add_argument("--model-revision")
    args = parser.parse_args()
    metadata = package(Path(__file__).resolve().parents[1],args.config,args.model_dir,args.model_revision)
    print(json.dumps({k:metadata[k] for k in ("run_id","snapshot_commit","config_path","tracks","planned_episodes","maximum_requests","result_directory")},indent=2))
