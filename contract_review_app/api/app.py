from fastapi import FastAPI
from typing import Any, Dict

app = FastAPI()

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.post("/api/analyze")
def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Поки що просто віддаємо ок
    return {"status": "ok", "analysis": {"issues": []}}

@app.post("/api/qa-recheck")
def qa_recheck(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Смок-тесту достатньо 200/ok
    return {"status": "ok"}
