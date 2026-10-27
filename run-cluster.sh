#!/bin/bash
# Run from Terminal, or double-click this file on macOS.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ARCHIVE=$ROOT/outputs/cluster-source.tar.gz
META=$ROOT/outputs/cluster-snapshot.json
STATE=$ROOT/outputs/cluster-last-run.json

case "${1:-}" in ""|--check|--new) ;; *) echo "Usage: $0 [--check|--new]"; exit 2 ;; esac
python3 - "$ROOT" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path
root = Path(sys.argv[1])
if not (root/'outputs/cluster-snapshot.json').is_file() or not (root/'outputs/cluster-source.tar.gz').is_file():
    raise SystemExit('Build the package first: uv run --locked python scripts/package_cluster.py')
meta = json.loads((root/'outputs/cluster-snapshot.json').read_text())
archive = root/'outputs/cluster-source.tar.gz'
if hashlib.sha256(archive.read_bytes()).hexdigest() != meta['archive_sha256']:
    raise SystemExit('Cluster archive checksum mismatch. Stop and rebuild the snapshot.')
if meta['termination_policy'] != 'first_failure' or meta['state_policy'] != 'initialize_once_then_successful_model_outputs':
    raise SystemExit('This archive does not contain the requested experiment protocol.')
if meta.get('rule_count') != 8:
    raise SystemExit('This launcher requires the eight-rule-only study snapshot.')
if meta.get('remind_previous_rules') is not True or meta.get('prompt_protocol_version') != 'cumulative_rule_reminders_v1':
    raise SystemExit('This launcher requires the study snapshot with previous-rule reminders.')
if meta.get('dataset_version') != 3 or meta.get('initialization_policy') != 'neutral_seed':
    raise SystemExit('Rebuild the neutral-seed v3 package: uv run --locked python scripts/package_cluster.py')
if meta.get('tracks') not in (['seeded'], ['order']):
    raise SystemExit('Package a seeded or order experiment with scripts/package_cluster.py')
h = hashlib.sha256()
for p in sorted((root/'src/passgame').glob('*.py')) + [root/'pyproject.toml', root/'uv.lock']:
    h.update(p.name.encode()); h.update(p.read_bytes())
if h.hexdigest() != meta['code_hash']:
    raise SystemExit('Code changed. Rebuild: uv run --locked python scripts/package_cluster.py')
with tarfile.open(archive) as bundle:
    packed = bundle.extractfile('passgame/configs/experiment.yaml').read()
if packed != (root/meta['config_path']).read_bytes():
    raise SystemExit('Configuration changed after packaging. Rebuild the study snapshot.')
print('Verified: v3 ' + meta['tracks'][0] + ' experiment, neutral starts, eight rules, reminders, stop on first failure.')
PY
if [ "${1:-}" = --check ]; then exit 0; fi

# Private settings stay local and are excluded from Git and source snapshots.
PRIVATE_CONFIG=${PASSGAME_CLUSTER_CONFIG:-$ROOT/configs/cluster.local.env}
if [ -f "$PRIVATE_CONFIG" ]; then source "$PRIVATE_CONFIG"; fi
: "${PASSGAME_SSH_HOST:?Set PASSGAME_SSH_HOST in the private cluster config}"
: "${PASSGAME_REMOTE_ROOT:?Set PASSGAME_REMOTE_ROOT in the private cluster config}"
: "${PASSGAME_ACCOUNT:?Set PASSGAME_ACCOUNT in the private cluster config}"
: "${PASSGAME_PARTITION:?Set PASSGAME_PARTITION in the private cluster config}"
HOST=$PASSGAME_SSH_HOST
REMOTE_ROOT=$PASSGAME_REMOTE_ROOT
ACCOUNT=$PASSGAME_ACCOUNT
PARTITION=$PASSGAME_PARTITION
GPU_RESOURCE=${PASSGAME_GPU_RESOURCE:-gpu:a100:1}
CPUS_PER_TASK=${PASSGAME_CPUS_PER_TASK:-4}
MEMORY=${PASSGAME_MEMORY:-48G}
TIME_LIMIT=${PASSGAME_TIME_LIMIT:-00:30:00}
SOCKET=${PASSGAME_SSH_SOCKET:-${TMPDIR:-/tmp}/passgame-cluster-$UID.sock}
case "$HOST" in *[!a-zA-Z0-9_.@-]*) echo 'Invalid SSH alias'; exit 1 ;; esac
case "$ACCOUNT:$PARTITION:$GPU_RESOURCE:$CPUS_PER_TASK:$MEMORY:$TIME_LIMIT" in *[!a-zA-Z0-9_.:-]*) echo 'Invalid scheduler settings'; exit 1 ;; esac
case "$REMOTE_ROOT" in /*) ;; *) echo 'Set an absolute remote workspace'; exit 1 ;; esac
SSH=(ssh -S "$SOCKET" -o BatchMode=yes -o ConnectTimeout=20 -o ForwardAgent=no "$HOST")

field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' "$1" "$2"; }
SNAPSHOT=$(field "$META" snapshot_commit)
RESULT_NAME=$(field "$META" result_directory)
case "$RESULT_NAME" in ""|*[!a-zA-Z0-9_.-]*) echo 'Invalid result directory'; exit 1 ;; esac
if [ -f "$STATE" ] && [ "${1:-}" != --new ]; then
    if [ "$(field "$STATE" snapshot_commit)" != "$SNAPSHOT" ]; then
        echo 'The saved run uses another snapshot. Use bash run-cluster.sh --new for a new evaluation.'
        exit 1
    fi
    REMOTE_RUN=$(field "$STATE" run_dir)
    JOB=$(field "$STATE" job_id)
else
    REMOTE_RUN=$REMOTE_ROOT/runs/predefined-stop-$(date -u +%Y%m%dT%H%M%SZ)-$$
    JOB=
fi
case "$REMOTE_RUN" in "$REMOTE_ROOT"/runs/predefined-stop-*) ;; *) echo 'Invalid saved run directory'; exit 1 ;; esac
case "$REMOTE_RUN" in *[!a-zA-Z0-9_./-]*) echo 'Invalid run directory characters'; exit 1 ;; esac
case "$JOB" in *[!0-9]*) echo 'Invalid saved job ID'; exit 1 ;; esac
save_state() {
    python3 - "$STATE" "$SNAPSHOT" "$REMOTE_RUN" "$JOB" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps(dict(snapshot_commit=sys.argv[2], run_dir=sys.argv[3], job_id=sys.argv[4]), indent=2)+'\n')
PY
}

if ! ssh -S "$SOCKET" -O check "$HOST" >/dev/null 2>&1; then
    echo 'Complete the cluster verification in this terminal. Do not send the code in chat.'
    ssh -M -S "$SOCKET" -o ControlPersist=30m -o ForwardAgent=no -fN "$HOST"
fi

if [ -z "$JOB" ]; then
    save_state
    # Recover a submitted job if the terminal closed before saving its ID.
    JOB=$("${SSH[@]}" "if [ -f '$REMOTE_RUN/job.id' ]; then cat '$REMOTE_RUN/job.id'; elif [ -e '$REMOTE_RUN/submission.started' ]; then exit 73; fi") || {
        echo "Submission status is uncertain. Inspect $REMOTE_RUN before starting another job."
        exit 1
    }
    if [ -z "$JOB" ]; then
        "${SSH[@]}" "mkdir -p '$REMOTE_RUN'"
        scp -o ControlPath="$SOCKET" -o BatchMode=yes "$ARCHIVE" "$HOST:$REMOTE_RUN/source.tar.gz"
        JOB=$("${SSH[@]}" "cd '$REMOTE_RUN' && bash -s -- '$ACCOUNT' '$PARTITION' '$GPU_RESOURCE' '$CPUS_PER_TASK' '$MEMORY' '$TIME_LIMIT'" <<'REMOTE'
set -euo pipefail
tar -xzf source.tar.gz
cd passgame
touch ../submission.started
job=$(sbatch --parsable --account="$1" --partition="$2" \
    --gres="$3" --cpus-per-task="$4" --mem="$5" --time="$6" \
    --job-name=passgame --output="$(dirname "$PWD")/evaluate-%j.log" \
    scripts/cluster/run_evaluation.sh)
printf '%s\n' "$job" > ../job.id
printf '%s\n' "$job"
REMOTE
        )
    fi
    case "$JOB" in ""|*[!0-9]*) echo 'Slurm did not return a valid job ID'; exit 1 ;; esac
    save_state
fi

echo "Cluster job: $JOB"
echo "Remote directory: $REMOTE_RUN"
echo 'Waiting for the pilot. If you close this window, run this file again to resume monitoring.'
RESULTS=$REMOTE_RUN/passgame/outputs/$RESULT_NAME
LAST_STATUS=
while :; do
    if "${SSH[@]}" "test -f '$RESULTS/completion.json'"; then break; fi
    STATUS=$("${SSH[@]}" "squeue -h -j '$JOB' -o '%T %R'")
    if [ -z "$STATUS" ]; then
        # Completion can appear between the first probe and the queue check.
        if "${SSH[@]}" "test -f '$RESULTS/completion.json'"; then break; fi
        "${SSH[@]}" "sacct -j '$JOB' -n -X -o JobID,State,ExitCode; tail -n 35 '$REMOTE_RUN/evaluate-$JOB.log'"
        echo "The job ended without a completion report. Logs remain in $REMOTE_RUN."
        exit 1
    fi
    if [ "$STATUS" != "$LAST_STATUS" ]; then echo "$STATUS"; LAST_STATUS=$STATUS; fi
    sleep 20
done

LOCAL_RESULTS=$ROOT/outputs/pilot-results-$JOB
mkdir -p "$LOCAL_RESULTS"
scp -r -o ControlPath="$SOCKET" -o BatchMode=yes "$HOST:$RESULTS" "$LOCAL_RESULTS/"
scp -o ControlPath="$SOCKET" -o BatchMode=yes "$HOST:$REMOTE_RUN/evaluate-$JOB.log" "$LOCAL_RESULTS/"
REPORT=$LOCAL_RESULTS/$RESULT_NAME
echo "Results downloaded to: $REPORT"
cat "$REPORT/completion.json"
cat "$REPORT/summary.csv"
python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["complete"] else 2)' "$REPORT/completion.json"
