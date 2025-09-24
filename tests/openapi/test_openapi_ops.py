import json


def test_operation_ids_unique():
    with open("openapi.json", encoding="utf-8") as f:
        spec = json.load(f)
    ids = []
    for path_item in spec.get("paths", {}).values():
        for op in path_item.values():
            if isinstance(op, dict) and op.get("operationId"):
                ids.append(op["operationId"])
    assert len(ids) == len(set(ids))
