from contract_review_app.document_checker import analyze_document
from contract_review_app.generate_report import generate_report  # ✅ оновлений імпорт

# 📦 Імітація прикладового контракту
contract_text = """
1. Term: This Agreement shall commence on 1 January 2023 and shall continue for a period of 2 years unless terminated earlier in accordance with this Agreement.
2. Confidentiality: Each Party agrees to keep confidential all information disclosed during the term of this Agreement.
3. Governing Law: This Agreement shall be governed by and construed in accordance with the laws of England and Wales.
"""

print("🔍 analyze_document: Start")
results = analyze_document(contract_text)

print(
    "🔍 Clauses extracted:", [r.metadata.get("clause_type", "unknown") for r in results]
)

# 📝 Генерація HTML-звіту
generate_report(results)  # ✅ Автоматично відкриває HTML-звіт

print("✅ Report generated successfully.")
