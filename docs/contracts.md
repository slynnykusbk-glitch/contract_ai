| Узел | Кто инициирует | URL | Запрос (минимум) | Ответ (минимум) | Заголовки | Версия |
| --- | --- | --- | --- | --- | --- | --- |
| Analyze | Клиент | `POST /api/analyze` | [`{text, mode?, schema:"1.4"}`](api.d.ts#L625-L660) | [AnalyzeResponse](api.d.ts#L661-L671) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| Draft | Клиент | `POST /api/gpt-draft` | [`{clause_id, text, ...}`](api.d.ts#L761-L775) | [`{draft_text, ...}`](api.d.ts#L816-L820) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| QA Recheck | Клиент | `POST /api/qa-recheck` | [`{text, ...}`](api.d.ts#L891-L909) | [QARecheckOut](api.d.ts#L911-L921) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| OpenAPI | Клиент | `GET /openapi.json` | [—](api.d.ts#L1) | [JSON](api.d.ts#L1) | — | — |
