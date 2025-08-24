from typing import Dict
from contract_review_app.core.schemas import AnalysisOutput

# 🔒 Шаблони редакцій за типами клаузул
REDACT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "Confidentiality": {
        "text": (
            "Each party shall keep all confidential information strictly confidential and shall not disclose "
            "such information to any third party without the prior written consent of the other party, "
            "except as required by law or regulation."
        ),
        "explanation": (
            "The revised clause clarifies that disclosure is only allowed with prior written consent or when legally required, "
            "which reduces legal uncertainty and aligns with best practices for confidentiality obligations."
        ),
    },
    "Indemnity": {
        "text": (
            "The Supplier shall indemnify and hold harmless the Customer from and against any and all claims, losses, "
            "liabilities, damages, and expenses (including legal fees) arising from the Supplier's breach of this Agreement, "
            "negligence, or wilful misconduct."
        ),
        "explanation": (
            "This revision provides a clear, standard indemnity covering breach, negligence, and misconduct, "
            "which ensures enforceability and mitigates unbounded liability risks."
        ),
    },
    "Termination": {
        "text": (
            "Either party may terminate this Agreement upon thirty (30) days' written notice to the other party. "
            "Termination shall not affect any rights or obligations accrued prior to the effective date."
        ),
        "explanation": (
            "This version introduces a clear notice period and preserves accrued rights, which is standard in commercial agreements."
        ),
    },
    "Force Majeure": {
        "text": (
            "Neither party shall be liable for any failure or delay in performance due to acts beyond their reasonable control, "
            "including natural disasters, war, terrorism, strikes, or governmental actions."
        ),
        "explanation": (
            "This clause outlines common force majeure events and limits liability in extraordinary circumstances."
        ),
    },
    "Governing Law": {
        "text": (
            "This Agreement shall be governed by and construed in accordance with the laws of England and Wales."
        ),
        "explanation": (
            "This clause clearly establishes the applicable legal jurisdiction, which reduces uncertainty in dispute resolution."
        ),
    },
    "Intellectual Property": {
        "text": (
            "All intellectual property rights arising from the performance of this Agreement shall remain the property "
            "of the originating party unless otherwise agreed in writing."
        ),
        "explanation": (
            "This clause protects each party’s existing IP and clarifies ownership of created IP."
        ),
    },
}


def enrich_with_redactions(output: AnalysisOutput, draft_text: str) -> str:
    """
    Якщо для даного типу клаузули є заздалегідь визначений шаблон, то він замінює draft_text.
    Інакше — повертає оригінальний draft_text.
    """
    clause_type = output.clause_type
    if clause_type in REDACT_TEMPLATES:
        return REDACT_TEMPLATES[clause_type]["text"]
    return draft_text
