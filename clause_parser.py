import re


def extract_clauses(doc_text):
    """
    Extracts numbered clauses (e.g., 1., 2., 10.) from the contract text.
    Returns a dictionary of clause_number: clause_text
    """
    clauses = {}
    current_clause = None
    lines = doc_text.splitlines()

    for line in lines:
        line = line.strip()
        if re.match(r"^\d{1,2}\.", line):
            current_clause = line
            clauses[current_clause] = line
        elif current_clause:
            clauses[current_clause] += "\n" + line

    return clauses


def check_indemnity_clause(clause_text):
    """
    Checks if indemnity clause has key components.
    """
    required_keywords = [
        "indemnifies",
        "loss",
        "liability",
        "costs",
        "breach",
        "non-performance",
    ]
    results = {"status": "✅ Complete", "missing": []}
    for kw in required_keywords:
        if kw.lower() not in clause_text.lower():
            results["missing"].append(kw)

    if results["missing"]:
        results["status"] = "❌ Incomplete"

    return results


def analyze_clauses(clauses):
    """
    Performs analysis on all clauses.
    """
    results = {}
    for number, text in clauses.items():
        if "indemnity" in text.lower():
            results[number] = check_indemnity_clause(text)
        # Future: check more types: termination, confidentiality, governing law, etc.
    return results
