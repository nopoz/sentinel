from functools import lru_cache
from pathlib import Path
import yaml

_POLICY_PATH = Path(__file__).resolve().parents[2] / "policy.yaml"


@lru_cache
def _policy() -> dict:
    return yaml.safe_load(_POLICY_PATH.read_text())


def _entry(action_type: str) -> dict:
    return _policy()["actions"].get(action_type, _policy()["default"])


def classify(action_type: str) -> str:
    return _entry(action_type)["class"]


def requires_approval(action_type: str) -> bool:
    return bool(_entry(action_type)["require_approval"])
