"""A pushed checkout must be able to reconstruct its launch artifacts."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest
import yaml


@pytest.mark.skipif(shutil.which("uv") is None,reason="The packaging CLI requires uv")
@pytest.mark.parametrize("track",["seeded","order"])
@pytest.mark.parametrize("port",[8000,18012])
def test_clean_checkout_can_build_and_check_progressive_snapshot(tmp_path,track,port):
    source = Path(__file__).resolve().parents[1]
    checkout = tmp_path/"checkout"
    checkout.mkdir()
    ignore = shutil.ignore_patterns("__pycache__","*.pyc",".pytest_cache","local","*.local.env","pilot-runtime.env")
    for name in ("src","tests","docs","configs","data","scripts"):
        shutil.copytree(source/name,checkout/name,ignore=ignore)
    for name in ("README.md","pyproject.toml","uv.lock",".gitignore",".python-version","run-pilot.sh","pilot.command"):
        shutil.copy2(source/name,checkout/name)
    assert not (checkout/"outputs").exists()
    missing = subprocess.run(["bash","run-pilot.sh","--check"],cwd=checkout,capture_output=True,text=True,timeout=10)
    assert missing.returncode != 0 and "scripts/package_pilot.py" in missing.stderr
    (checkout/"configs/cluster.local.env").write_text(
        'PASSGAME_REMOTE_ROOT=/cluster/workspace/passgame\n'
        'PASSGAME_SIF=/cluster/containers/runtime.sif\n'
        'PASSGAME_MODEL_DIR=/cluster/models/fixture-weights\n')
    config_name = "configs/dev-qwen2.5-7b-eight-rules.yaml" if track == "seeded" else "configs/dev-qwen2.5-7b-v3-order.yaml"
    config_path = checkout/config_name
    selected = yaml.safe_load(config_path.read_text())
    selected["models"][0]["base_url"] = f"http://127.0.0.1:{port}/v1"
    selected["models"][0]["parameters"]["chat_template_kwargs"] = {"enable_thinking":True}
    config_path.write_text(yaml.safe_dump(selected))
    result = subprocess.run(["uv","run","--locked","python","scripts/package_pilot.py","--config",config_name],cwd=checkout,
                            capture_output=True,text=True,timeout=120,env={**os.environ,"UV_OFFLINE":"1",
                            "PASSGAME_CLUSTER_CONFIG":str(checkout/"configs/cluster.local.env")})
    assert result.returncode == 0,result.stdout+result.stderr
    manifest = json.loads((checkout/"outputs/pilot-stop-on-failure-snapshot.json").read_text())
    assert manifest["dataset_version"] == 3 and manifest["initialization_policy"] == "neutral_seed"
    assert manifest["tracks"] == [track]
    assert manifest["planned_episodes"] == (24 if track == "seeded" else 96)
    assert manifest["maximum_requests"] == 8*manifest["planned_episodes"]
    assert manifest["port"] == port
    assert manifest["generation_parameters"]["chat_template_kwargs"] == {"enable_thinking":True}
    archive = checkout/"outputs/pilot-stop-on-failure.tar.gz"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive_sha256"]
    with tarfile.open(archive) as bundle:
        names = bundle.getnames()
        assert "passgame/scripts/run_galvani_fixed_start.sh" in names
        assert "passgame/data/sequential-v3/development-games.txt" in names
        assert "passgame/configs/cluster.local.env" not in names
        assert not any("/.venv/" in p for p in names)
        config = bundle.extractfile("passgame/configs/experiment.yaml").read().decode()
        runtime = bundle.extractfile("passgame/configs/pilot-runtime.env").read().decode()
        parsed = yaml.safe_load(config)
        assert parsed["dataset_dir"] == "data/sequential-v3" and parsed["tracks"] == [track]
        assert parsed["models"][0]["base_url"] == f"http://127.0.0.1:{port}/v1"
        assert parsed["models"][0]["parameters"]["chat_template_kwargs"] == {"enable_thinking":True}
        assert "SERVED_NAME=qwen2.5-7b-instruct" in runtime
        assert f"PORT={port}\n" in runtime
        wrapper = bundle.extractfile("passgame/scripts/run_galvani_fixed_start.sh").read().decode()
        assert "export SIF MODEL_DIR SERVED_NAME MAX_MODEL_LEN PORT" in wrapper
    snapshot = checkout/"outputs/launches"/manifest["run_id"]/"passgame"
    tracked = subprocess.check_output(["git","ls-files"],cwd=snapshot,text=True).splitlines()
    assert "configs/cluster.local.env" not in tracked and "configs/pilot-runtime.env" not in tracked
    for name in ("run-pilot.sh","pilot.command"):
        checked = subprocess.run(["bash",name,"--check"],cwd=checkout,capture_output=True,text=True,timeout=10)
        assert checked.returncode == 0,checked.stdout+checked.stderr


def test_packager_requires_explicit_weights_for_a_new_model(tmp_path):
    import importlib.util
    import yaml
    source = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("package_pilot",source/"scripts/package_pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = yaml.safe_load((source/"configs/dev-qwen2.5-7b-eight-rules.yaml").read_text())
    config["models"][0]["model_id"] = "a-different-open-model"
    path = tmp_path/"model.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError,match="renaming Qwen does not change its weights"):
        module.package(tmp_path,Path("model.yaml"))
    with pytest.raises(ValueError,match="Record --model-revision"):
        module.package(tmp_path,Path("model.yaml"),"/models/new-model")
    assert not (tmp_path/"outputs").exists()
