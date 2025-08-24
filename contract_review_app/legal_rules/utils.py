from contract_review_app.core.schemas import Finding

def score_from_findings(findings: list[Finding]) -> int:
    """
    Обчислює ризикову оцінку (0–100) на підставі рівнів severity у findings.
    """
    score = 100
    for f in findings:
        if f.severity == "critical":
            score -= 50
        elif f.severity == "high":
            score -= 30
        elif f.severity == "medium":
            score -= 15
        elif f.severity == "low":
            score -= 5
    return max(score, 0)
