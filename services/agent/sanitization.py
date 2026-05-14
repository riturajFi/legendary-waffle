from typing import Any


SENSITIVE_HINT_KEYS = {"scenario", "_scenario"}


def strip_scenario_hints(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_scenario_hints(child)
            for key, child in value.items()
            if key not in SENSITIVE_HINT_KEYS
        }

    if isinstance(value, list):
        return [strip_scenario_hints(item) for item in value]

    return value
