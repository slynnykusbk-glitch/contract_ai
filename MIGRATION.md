# Migration Guide — Doctor v2 (14-block matrix) & Block B5: Legal Corpus

Документ описывает:
1) как обновлённый **Doctor v2** собирает диагностику и показывает **матрицу зрелости из 14 блоков (B0…B13)**;
2) базовые понятия и схему для **B5 — Legal Corpus & Metadata**.

---

## Doctor v2 — 14-block maturity matrix

Doctor v2 собирает техническую диагностику проекта (env, git, quality, api, rules, add-in, llm и др.) и формирует отчёт с матрицей состояния 14 блоков.

### Запуск

```bash
python tools/doctor.py --out reports/latest/analysis --json --html
