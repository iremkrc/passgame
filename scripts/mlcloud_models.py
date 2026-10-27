"""List model IDs visible to a Tübingen ML Cloud key without running inference."""

import argparse
import os
import sys

import httpx


BASE_URL = "https://llm.mlcloud.uni-tuebingen.de/v1"


def list_models(api_key_env: str = "TUEBINGEN_API_KEY", *, transport=None) -> list[str]:
    key = os.environ.get(api_key_env)
    if not key:
        raise ValueError(f"Set the credential environment variable {api_key_env} first")
    with httpx.Client(timeout=30, transport=transport) as client:
        response = client.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {key}"})
    if response.status_code != 200:
        raise ValueError(f"Model discovery returned HTTP {response.status_code}; check your key, access, and endpoint")
    try:
        data = response.json()["data"]
        if not isinstance(data, list):
            raise ValueError
        models = [model["id"] for model in data]
        if any(not isinstance(model, str) or not model.strip() for model in models):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("Model discovery returned an invalid model list") from None
    return sorted(set(models))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key-env", default="TUEBINGEN_API_KEY", help="Environment variable containing the key")
    args = parser.parse_args()
    try:
        models = list_models(args.api_key_env)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except httpx.TransportError:
        print("Cannot reach ML Cloud; check your network and endpoint", file=sys.stderr)
        return 1
    if not models:
        print("The key has no visible models", file=sys.stderr)
        return 1
    for model in models:
        print(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
