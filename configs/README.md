# Study configurations

- `api/`: seven hosted-model conditions, using the credential named by `api_key_env`.
- `cluster/`: twelve self-hosted conditions, with zero API-token prices.
- `cluster.example.env`: private SSH, scheduler, image, and weight settings template.

Each YAML specifies the complete model condition, study selection, output path,
response-parsing policy, generation parameters, budget, and analysis settings.
Run commands from the repository root; data paths are relative to that directory.
The [run index](../results/RUNS.md) maps configurations to reported evidence.

For a new endpoint or modified condition, copy a configuration to an ignored
`*.local.yaml`, edit the endpoint/model and pricing/budget fields, and choose a
unique study/output directory. Model weights must match the served name; changing
a model ID alone does not change a server's weights. Never store credential values
in YAML. [Reproduction instructions](../docs/reproducibility.md) cover both routes.
