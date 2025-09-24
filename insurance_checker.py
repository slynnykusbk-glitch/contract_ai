import json
import re
from pathlib import Path
from typing import Any, Dict

import yaml


def normalize(text: str) -> str:
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for src, tgt in replacements.items():
        text = text.replace(src, tgt)
    text = re.sub(r"\s+", " ", text)
    return text


def _apply_transform(value: str, transform: str) -> Any:
    if transform == "to_int":
        try:
            return int(value)
        except ValueError:
            return None
    if transform == "to_float":
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return value


def _detect_value(text: str, rule: Dict[str, Any]) -> Any:
    flags = re.IGNORECASE | re.DOTALL
    if "regex" in rule:
        return bool(re.search(rule["regex"], text, flags))
    if "regex_group" in rule:
        rg = rule["regex_group"]
        m = re.search(rg["pattern"], text, flags)
        if m:
            val = m.group(int(rg["group"]))
            transform = rg.get("transform")
            if transform:
                return _apply_transform(val, transform)
            return val
        return None
    if "any" in rule:
        results = set()
        found = False
        for item in rule["any"]:
            if re.search(item["regex"], text, flags):
                if "value" in item:
                    results.add(item["value"])
                else:
                    found = True
        if results:
            return sorted(results)
        return found
    if "all" in rule:
        for item in rule["all"]:
            if not re.search(item["regex"], text, flags):
                return False
        return True
    if "cases" in rule:
        for case in rule["cases"]:
            when = case.get("when")
            if when and when.lower() in text.lower():
                return case["value"]
            when_regex = case.get("when_regex")
            if when_regex and re.search(when_regex, text, flags):
                return case["value"]
        for case in rule["cases"]:
            if "default" in case:
                return case["default"]
        return None
    return None


def detect(text: str, detect_rules: Dict[str, Any]) -> Dict[str, Any]:
    extract: Dict[str, Any] = {}
    for key, rule in detect_rules.items():
        extract[key] = _detect_value(text, rule)
    return extract


def _compare(value: Any, rule: Dict[str, Any]) -> bool:
    if "expect" in rule:
        return value == rule["expect"]
    op = rule.get("op")
    target = rule.get("value")
    if op == "gte":
        try:
            return float(value) >= float(target)
        except (TypeError, ValueError):
            return False
    if op == "ne":
        return value != target
    if op == "contains_any":
        if not isinstance(value, (list, set, tuple)):
            return False
        return any(v in value for v in target)
    return False


def validate(extract: Dict[str, Any], validate_rules: Dict[str, Any]) -> Dict[str, Any]:
    hard_results = []
    soft_results = []
    hard_fail_count = 0
    soft_warn_count = 0

    for rule in validate_rules.get("hard", []):
        key = rule["key"]
        got = extract.get(key)
        status = "PASS" if _compare(got, rule) else "FAIL"
        res = {"key": key, "status": status}
        if status == "FAIL":
            res["got"] = got
            if "fail_message" in rule:
                res["message"] = rule["fail_message"]
            hard_fail_count += 1
        hard_results.append(res)

    for rule in validate_rules.get("soft", []):
        key = rule["key"]
        got = extract.get(key)
        status = "PASS" if _compare(got, rule) else "WARN"
        res = {"key": key, "status": status}
        if status == "WARN":
            res["got"] = got
            if rule.get("op") == "gte":
                res["hint"] = f">={rule['value']}"
            elif rule.get("op") == "ne":
                res["hint"] = f"!= {rule['value']}"
            elif rule.get("op") == "contains_any":
                res["hint"] = f"contains any of {rule['value']}"
            if "warn_message" in rule:
                res["message"] = rule["warn_message"]
            soft_warn_count += 1
        soft_results.append(res)

    return {
        "hard": hard_results,
        "soft": soft_results,
        "summary": {
            "hard_fail_count": hard_fail_count,
            "soft_warn_count": soft_warn_count,
        },
    }


def check(text: str, rulepack_path: str = "insurance_rulepack.yaml") -> Dict[str, Any]:
    rp = yaml.safe_load(Path(rulepack_path).read_text(encoding="utf-8"))
    norm_text = normalize(text)
    extract = detect(norm_text, rp.get("detect", {}))
    validation = validate(extract, rp.get("validate", {}))
    result = {"extract": extract, **validation}
    return result


def check_file(
    path: str, rulepack_path: str = "insurance_rulepack.yaml"
) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return check(text, rulepack_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: insurance_checker.py <path>")
        sys.exit(1)
    res = check_file(sys.argv[1])
    print(json.dumps(res, ensure_ascii=False, indent=2))
