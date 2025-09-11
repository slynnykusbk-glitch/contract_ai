# RUNBOOK

## Setup

Install dependencies and confirm **PyYAML** is installed so `/api/analyze` can parse rule packs:

```bash
pip install -r requirements.txt
python -c "import yaml"
```

## Build add-in (Windows)

```bash
cd word_addin_dev && npm ci && npm test && npm run build
cd .. && npm run build:panel
```

## Panel (HTTPS 3000)
python .\word_addin_dev\serve_https_panel.py 
  --root "C:\Users\Ludmila\contract_ai\word_addin_dev" 
  --host 127.0.0.1 --port 3000 
  --cert "C:\Users\Ludmila\contract_ai\word_addin_dev\certs\localhost.pem" 
  --key  "C:\Users\Ludmila\contract_ai\word_addin_dev\certs\localhost-key.pem"

## Backend (HTTPS 9443)
.\.venv\Scripts\Activate.ps1
="C:\Users\Ludmila\contract_ai\word_addin_dev\certs\localhost.pem"
 ="C:\Users\Ludmila\contract_ai\word_addin_dev\certs\localhost-key.pem"
uvicorn contract_review_app.api.app:app --host 127.0.0.1 --port 9443 
  --ssl-certfile "" --ssl-keyfile "" --reload

## Smoke tests
curl -k https://127.0.0.1:9443/health
curl -k -X POST https://127.0.0.1:9443/api/analyze -H "Content-Type: application/json" 
  -d "{\"text\":\"This agreement is governed by the laws of England and Wales.\"}"
