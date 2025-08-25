from __future__ import annotations
import re
from typing import List, Dict


def _extract_defined_terms(text: str) -> List[str]:
    pattern = re.compile(r'"([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*)"\s+(?:means|shall mean|is defined as)', re.IGNORECASE)
    return [m.group(1) for m in pattern.finditer(text or "")]


def _extract_capitalised_terms(text: str) -> List[str]:
    # Capture multi-word Capitalised terms (e.g., "Process Agent")
    pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
    return [m.group(1) for m in pattern.finditer(text or "")]


def run(text: str) -> List[Dict[str, str]]:
    """Run integrity checks on full document text and return findings."""
    findings: List[Dict[str, str]] = []
    lower = text.lower() if isinstance(text, str) else ""

    # --- exhibits_LM_referenced ---
    if "exhibit l" in lower or "exhibit m" in lower:
        has_l = "exhibit l" in lower
        has_m = "exhibit m" in lower
        if not (has_l and has_m):
            findings.append({
                "rule_id": "exhibits_LM_referenced",
                "severity": "high",
                "message": "Both Exhibit L and Exhibit M should be referenced at least once.",
            })

    # Extract defined and used terms
    defined_terms = set(_extract_defined_terms(text))
    cap_terms = _extract_capitalised_terms(text)
    cap_counts: Dict[str, int] = {}
    for term in cap_terms:
        cap_counts[term] = cap_counts.get(term, 0) + 1

    # --- definitions_undefined_used ---
    for term, count in cap_counts.items():
        if term not in defined_terms and count > 0:
            findings.append({
                "rule_id": "definitions_undefined_used",
                "severity": "major",
                "message": f"'{term}' used but not defined.",
            })

    # --- definitions_unused_defined ---
    for term in defined_terms:
        occurrences = len(re.findall(rf'\b{re.escape(term)}\b', text))
        if occurrences <= 1:
            findings.append({
                "rule_id": "definitions_unused_defined",
                "severity": "minor",
                "message": f"'{term}' defined but not used.",
            })

    # --- numbering_gaps_duplicates ---
    numbers = [int(m.group(1)) for m in re.finditer(r'^\s*(\d+)\.', text, flags=re.MULTILINE)]
    expected = 1
    for n in numbers:
        if n != expected:
            findings.append({
                "rule_id": "numbering_gaps_duplicates",
                "severity": "major",
                "message": "Clause numbering has gaps or duplicates.",
            })
            break
        expected += 1

    # --- schedule_appendix_links ---
    if re.search(r'\b(appendix|exhibit)\s+[A-Z0-9]+', text, flags=re.IGNORECASE):
        if not re.search(r'\battached\b', text, flags=re.IGNORECASE):
            findings.append({
                "rule_id": "schedule_appendix_links",
                "severity": "major",
                "message": "Schedule/Appendix referenced but not indicated as attached.",
            })

    return findings
