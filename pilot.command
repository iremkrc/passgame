#!/bin/bash
# Run from Terminal, or double-click this file on macOS.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ARCHIVE=$ROOT/outputs/pilot-stop-on-failure.tar.gz
META=$ROOT/outputs/pilot-stop-on-failure-snapshot.json
STATE=$ROOT/outputs/pilot-last-run.json
SOCKET=/tmp/passgame-galvani.sock
REMOTE_ROOT=/mnt/lustre/work/eickhoff/esx797/passgame
SSH=(ssh -S "$SOCKET" -o BatchMode=yes -o ConnectTimeout=20 -o ForwardAgent=no galvani)

case "${1:-}" in ""|--check|--new) ;; *) echo "Usage: $0 [--check|--new]"; exit 2 ;; esac
python3 - "$ROOT" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path
root = Path(sys.argv[1])
meta = json.loads((root/'outputs/pilot-stop-on-failure-snapshot.json').read_text())
archive = root/'outputs/pilot-stop-on-failure.tar.gz'
if hashlib.sha256(archive.read_bytes()).hexdigest() != meta['archive_sha256']:
    raise SystemExit('Pilot archive checksum mismatch. Stop and rebuild the snapshot.')
if meta['termination_policy'] != 'first_failure' or meta['state_policy'] != 'initialize_once_then_successful_model_outputs':
    raise SystemExit('This archive does not contain the requested experiment protocol.')
if meta.get('rule_count') != 8:
    raise SystemExit('This launcher requires the eight-rule-only pilot snapshot.')
if meta.get('remind_previous_rules') is not True or meta.get('prompt_protocol_version') != 'cumulative_rule_reminders_v1':
    raise SystemExit('This launcher requires the pilot snapshot with previous-rule reminders.')
h = hashlib.sha256()
for p in sorted((root/'src/passgame').glob('*.py')) + [root/'pyproject.toml', root/'uv.lock']:
    h.update(p.name.encode()); h.update(p.read_bytes())
if h.hexdigest() != meta['code_hash']:
    raise SystemExit('Code changed after packaging. Ask Codex to rebuild the pilot snapshot.')
with tarfile.open(archive) as bundle:
    packed = bundle.extractfile('passgame/configs/experiment.yaml').read()
if packed != (root/meta['config_path']).read_bytes():
    raise SystemExit('Configuration changed after packaging. Rebuild the pilot snapshot.')
print('Verified: eight-rule games, previous-rule reminders, predefined initial strings, model-driven progression, stop on first failure.')
PY
if [ "${1:-}" = --check ]; then exit 0; fi

field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' "$1" "$2"; }
SNAPSHOT=$(field "$META" snapshot_commit)
RESULT_NAME=$(field "$META" result_directory)
case "$RESULT_NAME" in ""|*[!a-zA-Z0-9_.-]*) echo 'Invalid result directory'; exit 1 ;; esac
if [ -f "$STATE" ] && [ "${1:-}" != --new ]; then
    if [ "$(field "$STATE" snapshot_commit)" != "$SNAPSHOT" ]; then
        echo 'The saved run uses another snapshot. Use ./pilot.command --new for a new pilot.'
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

if ! ssh -S "$SOCKET" -O check galvani >/dev/null 2>&1; then
    echo 'Complete the Galvani verification in this terminal. Do not send the code in chat.'
    ssh -M -S "$SOCKET" -o ControlPersist=30m -o ForwardAgent=no -fN galvani
fi

if [ -z "$JOB" ]; then
    save_state
    # Recover a submitted job if the terminal closed before saving its ID.
    JOB=$("${SSH[@]}" "if [ -f '$REMOTE_RUN/job.id' ]; then cat '$REMOTE_RUN/job.id'; elif [ -e '$REMOTE_RUN/submission.started' ]; then exit 73; fi") || {
        echo "Submission status is uncertain. Ask Codex to inspect $REMOTE_RUN before starting another job."
        exit 1
    }
    if [ -z "$JOB" ]; then
        "${SSH[@]}" "mkdir -p '$REMOTE_RUN'"
        scp -o ControlPath="$SOCKET" -o BatchMode=yes "$ARCHIVE" "galvani:$REMOTE_RUN/source.tar.gz"
        JOB=$("${SSH[@]}" "cd '$REMOTE_RUN' && bash -s" <<'REMOTE'
set -euo pipefail
tar -xzf source.tar.gz
cd passgame
touch ../submission.started
job=$(sbatch --parsable --account=eickhoff --partition=a100-galvani \
    --gres=gpu:a100:1 --cpus-per-task=4 --mem=48G --time=00:30:00 \
    --job-name=passgame-pilot --output="$(dirname "$PWD")/evaluate-%j.log" \
    scripts/run_galvani_fixed_start.sh)
printf '%s\n' "$job" > ../job.id
printf '%s\n' "$job"
REMOTE
        )
    fi
    case "$JOB" in ""|*[!0-9]*) echo 'Slurm did not return a valid job ID'; exit 1 ;; esac
    save_state
fi

echo "Pilot job: $JOB"
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
scp -r -o ControlPath="$SOCKET" -o BatchMode=yes "galvani:$RESULTS" "$LOCAL_RESULTS/"
scp -o ControlPath="$SOCKET" -o BatchMode=yes "galvani:$REMOTE_RUN/evaluate-$JOB.log" "$LOCAL_RESULTS/"
REPORT=$LOCAL_RESULTS/$RESULT_NAME
echo "Results downloaded to: $REPORT"
cat "$REPORT/completion.json"
cat "$REPORT/summary.csv"
python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["complete"] else 2)' "$REPORT/completion.json"
