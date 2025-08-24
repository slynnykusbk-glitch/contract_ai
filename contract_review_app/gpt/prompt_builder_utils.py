# 📄 contract_review_app/gpt/prompt_builder_utils.py

from contract_review_app.core.schemas import AnalysisOutput

def build_prompt(analysis: AnalysisOutput) -> str:
    """
    ✅ Alias: build_prompt_for_clause(analysis)
    Builds a GPT prompt to rewrite a clause based on rule-based analysis results.
    """
    clause_type = analysis.clause_type or "Unknown Clause"
    status = analysis.status or "UNKNOWN"
    recommendations = analysis.recommendations or []
    findings = analysis.findings or []
    diagnostics = analysis.diagnostics or []
    original_text = analysis.text or ""

    explanation = (
        "You are a legal drafting assistant. "
        "Your task is to rewrite the clause below to align with legal standards under UK law, "
        "preserve legal clarity, reduce legal risk, and reflect the provided findings and recommendations. "
        "Do not include any commentary or metadata. Only output the revised clause text.\n"
    )

    header = f"Clause Type: {clause_type}\nStatus: {status}\n\n"

    findings_section = (
        "Findings:\n" + "\n".join(
            f"- [{f.severity or 'info'}] {f.message}" for f in findings
        )
        if findings else ""
    )

    recommendations_section = (
        "Recommendations:\n" + "\n".join(
            f"- {r}" for r in recommendations
        )
        if recommendations else ""
    )

    diagnostics_section = (
        "Diagnostics:\n" + "\n".join(diagnostics)
        if diagnostics else ""
    )

    clause_section = f"\n\nOriginal Clause:\n---\n{original_text.strip()}\n---\n"

    prompt = (
        explanation
        + header
        + (findings_section + "\n\n" if findings else "")
        + (recommendations_section + "\n\n" if recommendations else "")
        + (diagnostics_section + "\n\n" if diagnostics else "")
        + clause_section
        + "\nPlease provide the improved clause text only:"
    )

    return prompt.strip()
