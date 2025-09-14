| Узел | Кто инициирует | URL | Запрос (минимум) | Ответ (минимум) | Заголовки | Версия |
| --- | --- | --- | --- | --- | --- | --- |
| Analyze | Клиент | `POST /api/analyze` | [`{text, mode?, schema:"1.4"}`](api.d.ts#L625-L660) | [AnalyzeResponse](api.d.ts#L661-L671) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| Draft | Клиент | `POST /api/gpt-draft` | [`{clause_id, text, ...}`](api.d.ts#L905-L921) | [`{draft_text, ...}`](api.d.ts#L3436-L3438) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| QA Recheck | Клиент | `POST /api/qa-recheck` | [`{document_id, ...}`](api.d.ts#L792-L811) | [Findings[]](api.d.ts#L922-L941) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| OpenAPI | Клиент | `GET /openapi.json` | [—](api.d.ts#L1) | [JSON](api.d.ts#L1) | — | — |
