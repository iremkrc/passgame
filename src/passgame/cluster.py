"""Read private deployment values without embedding personal paths in source."""

import os
from pathlib import Path
import re
import shlex


def settings(root: Path) -> dict[str,str]:
    """Local literal assignments override environment values; do not evaluate code."""
    result = {k:v for k,v in os.environ.items() if k.startswith("PASSGAME_")}
    path = Path(os.environ.get("PASSGAME_CLUSTER_CONFIG",str(root/"configs/cluster.local.env")))
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"PASSGAME_[A-Z0-9_]+",key):
            raise ValueError("Use PASSGAME_KEY=VALUE assignments in the private cluster configuration")
        try:
            values = shlex.split(value,comments=True)
        except ValueError:
            raise ValueError("Invalid quoting in the private cluster configuration") from None
        if len(values) > 1:
            raise ValueError("Quote values containing spaces in the private cluster configuration")
        result[key] = values[0] if values else ""
    return result


def required(values: dict[str,str], key: str) -> str:
    value = values.get(key,"")
    if not value or value.startswith("YOUR_") or value.startswith("/path/to/"):
        raise ValueError(f"Set {key} in configs/cluster.local.env using configs/cluster.example.env")
    return value
