from typing import Any, Dict, List, Optional


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


def path_to_dict(path: Optional[Any]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None

    return {
        "nodes": [node_to_dict(node) for node in path.nodes],
        "relationships": [relationship_to_dict(rel) for rel in path.relationships],
    }


def relationship_to_dict(relationship: Any) -> Dict[str, Any]:
    return {
        "type": relationship.type,
        "start_node_id": relationship.start_node.get("id"),
        "end_node_id": relationship.end_node.get("id"),
        "properties": dict(relationship),
    }


__all__: List[str] = [
    "node_to_dict",
    "path_to_dict",
    "relationship_to_dict",
    "serialize_neo4j_value",
]
