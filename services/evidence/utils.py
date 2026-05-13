from typing import Any, Dict, Optional


def node_to_dict(node: Optional[Any]) -> Optional[Dict[str, Any]]:
    if node is None:
        return None

    data = dict(node)

    for key, value in data.items():
        data[key] = serialize_neo4j_value(value)

    return data


def serialize_neo4j_value(value: Any) -> Any:
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()

    return value


__all__ = ["node_to_dict", "serialize_neo4j_value"]
