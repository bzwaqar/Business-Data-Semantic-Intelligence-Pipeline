# CSV Classifier

FastAPI application for CSV processing and text classification.

## Features
- Health check endpoint (`GET /api/v1/health`)
- Configuration management via environment variables using `pydantic-settings`

## Project Structure

```
csv-classifier/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── health.py
│   ├── services/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   └── core/
│       └── __init__.py
├── jobs/
│   └── .gitkeep
├── requirements.txt
├── .env.example
├── Dockerfile
└── README.md
```

## Getting Started

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints

- `GET /api/v1/health` -> `{"status": "ok"}`

## Docker

```bash
docker build -t csv-classifier .
docker run -p 8000:8000 csv-classifier
```
