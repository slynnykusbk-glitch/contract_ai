from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/analyze")
def analyze(payload: dict):
    return {"status": "ok", "result": {}}

@app.post("/api/qa-recheck")
def qa_recheck(payload: dict):
    return {"status": "ok"}
