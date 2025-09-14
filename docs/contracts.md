| Узел | Кто инициирует | URL | Запрос (минимум) | Ответ (минимум) | Заголовки | Версия |
| --- | --- | --- | --- | --- | --- | --- |
| Analyze | Клиент | `POST /api/analyze` | [`{text, mode?, schema:"1.4"}`](../word_addin_dev/app/types/api.d.ts#L625-L660) | [AnalyzeResponse](../word_addin_dev/app/types/api.d.ts#L661-L671) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| Draft | Клиент | `POST /api/gpt-draft` | [`{clause_id, text, ...}`](../word_addin_dev/app/types/api.d.ts#L905-L921) | [`{draft_text, ...}`](../word_addin_dev/app/types/api.d.ts#L3436-L3438) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| QA Recheck | Клиент | `POST /api/qa-recheck` | [`{document_id, ...}`](../word_addin_dev/app/types/api.d.ts#L792-L811) | [Findings[]](../word_addin_dev/app/types/api.d.ts#L922-L941) | `Content-Type: application/json`<br>`X-Schema-Version: 1.4` | `1.4` |
| OpenAPI | Клиент | `GET /openapi.json` | [—](../word_addin_dev/app/types/api.d.ts#L1) | [JSON](../word_addin_dev/app/types/api.d.ts#L1) | — | — |
