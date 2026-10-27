# Study scripts

| Entry point | Purpose |
| --- | --- |
| `python -m passgame.run` | Preflight or evaluate an API/self-hosted model; saves analysis automatically |
| `python -m passgame.analyze` | Analyze saved responses with explicit bootstrap settings |
| `python -m passgame.generate` | Generate the synthetic study dataset |
| `python -m passgame.export` | Export readable rules and the audit worksheet |
| `mlcloud_models.py` | List model IDs accessible to a provider account |
| `package_cluster.py` | Freeze source/config/data and construct a cluster launch snapshot |
| `cluster/serve_and_eval.sh` | Start vLLM, evaluate configurations, stop the server |
| `cluster/slurm.example.sbatch` | Scheduler template for the serving helper |
| Model-specific `.sbatch` files | GPU/parser/resource settings for reported conditions |
| Root `run-cluster.sh` | Submit or resume monitoring a packaged cluster job |

Run from the repository root. Site-specific values belong in ignored private
configuration files. See [reproducibility](../docs/reproducibility.md).
