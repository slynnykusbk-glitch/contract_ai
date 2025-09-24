# Contract AI — MASTER RUNBOOK & REQUIREMENTS (v1.0)

> Оновлено: 2025-08-12. Це єдиний довідник, який описує **як ми запускаємо систему**, **де перевіряємо**, **який контракт API**, **які вимоги до коду/структури**, і **як діагностуємо**. Основано на останніх виправленнях і узгодженому підході.

---

## 1) Огляд архітектури

- **Frontend (Word Add-in):**
  - `taskpane.html` + `taskpane.bundle.js` (папка `word_addin_dev/` або корінь веб-серверу).
  - Працює проти бекенда за HTTPS.
- **Backend (FastAPI):**
  - Ендпойнти:
    - `GET /health` — стан і список правил.
    - `POST /api/analyze` — аналіз клаузули/документа.
    - `POST /api/gpt/draft` — безпечна заглушка для кнопки “Get AI Draft”.
    - `GET /api/trace/{cid}` — трасування запитів за `x-cid` (dev).
  - CORS увімкнено для локальної панелі (127.0.0.1/127.0.0.1) + `Origin: null` (self-test).

- **Rules Engine (Pipeline):**
  - Дискавері правил із `contract_review_app/legal_rules/rules/*.py`.
  - Уніфікований вихід (`AnalysisOutput`) → узагальнений `analysis` для UI.

- **Doctor v2 (автоматична перевірка):**
  - Перевіряє **FRONT → TLS/CORS → API → PIPELINE/RULES → JSON/Schema → UI**.
  - Вивід у `report/doctor_report-YYYYMMDD-HHMMSS.md` + `.json` + `.console.log`.

---

## 2) Як запускати локально

### 2.1 Сертифікат (разово)
1. `python gen_dev_cert.py`
2. Імпортуй `C:\certs\dev.crt` у *Trusted Root Certification Authorities*.
> Використовуй `https://127.0.0.1:9000` (або додай 127.0.0.1 у SAN сертифіката).

### 2.2 Бекенд
```
uvicorn contract_review_app.api.app:app --host 127.0.0.1 --port 9000 ^
  --ssl-keyfile "C:\certs\dev.key" ^
  --ssl-certfile "C:\certs\dev.crt"
```
Перевірка: https://127.0.0.1:9000/health → `{"status":"ok","rules":[...],"count":N}`.

### 2.3 Front (панель)
- HTTPS сервер на 3000 (наприклад, `http-server -S`).
- URL бекенда в панелі: **https://127.0.0.1:9000**.

### 2.4 Self-test
Відкрити `word_addin_dev/panel_selftest.html` → Backend URL `https://127.0.0.1:9000` → **Run**.
Очікуємо: `GET /health -> 200`, `POST /api/analyze -> 200`, `analysis ok`.

### 2.5 Doctor v2
`RUN_DOCTOR.bat` → звіт у `report/doctor_report-*.md|json|console.log`.

---

## 3) Контракт API

### POST /api/analyze
Request:
```
{ "text": "<clause text>", "clause_type": "optional" }
```
Response:
```
{
  "analysis": { "clause_type": "...", "findings": [...], "recommendations": [...],
                "proposed_text": "", "score": 0, "risk": "low|medium|high",
                "severity": "low|medium|high", "status": "OK|WARN|FAIL" },
  "results": { "<rule>": { ...AnalysisOutput... } },
  "clauses": [ { "type": "<rule>", "text": "<source>" } ]
}
```

---

## 4) Структура проєкту ( essentials )
contract_review_app/
- api/app.py            — FastAPI (health/analyze/draft/trace)
- engine/pipeline.py    — discover_rules(), analyze_document()
- legal_rules/rules/*   — модулі правил (confidentiality.py тощо)
- core/schemas.py       — AnalysisInput/Output, Finding, AnalyzeResponse

word_addin_dev/
- taskpane.html, taskpane.bundle.js, panel_selftest.html

report/
- doctor_report-*.md|json|console.log

---

## 5) Вимоги до правил
Функція `analyze(inp: AnalysisInput) -> AnalysisOutput` і **жодних «голих dict»**.
Обов’язково: `findings` — список, `message` у кожному finding, статус ∈ {OK,WARN,FAIL}.

---

## 6) Типові збої і рішення
- Порожня сторінка /health → відкрито `https://127.0.0.1:9000`, а сертифікат на `127.0.0.1`. Відкрий `https://127.0.0.1:9000` або перевипусти серт із SAN:127.0.0.1.
- Rules=0 → немає `__init__.py` або правила не в `legal_rules/rules`.
- 500 на /api/analyze → синтаксична помилка в pipeline/rule; дивись Doctor та /api/trace/{cid}.
- `Clause type: unknown` у UI → немає плоского `analysis` (виправлено в app.py).

---

## 7) Реліз/Безпека
- Після дебагу звузити CORS (прибрати `"null"`).
- Прикрити /api/trace/* (auth/feature-flag).
- Версіонувати API (/v1/...).

---

## 8) Команди-шпаргалка
- Бекенд: див. 2.2
- Self-test: file:///.../word_addin_dev/panel_selftest.html → Backend=https://127.0.0.1:9000
- Doctor: RUN_DOCTOR.bat
