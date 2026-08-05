<div align="center">
  <h1>🚀 Business Data Semantic Intelligence Pipeline</h1>
  <p><strong>A full-stack, AI-powered system for intelligent CSV text classification and data grouping.</strong></p>
</div>

<br/>

## ✨ Overview

This project is an automated AI pipeline designed to ingest messy business CSV data, understand the semantic meaning of the text, cluster similar items together, and automatically assign them intelligent category names using Large Language Models (LLMs). 

It features a robust **FastAPI** backend that runs background jobs, and a sleek, fast **React + Vite** frontend for a seamless user experience.

---

## 🛠️ Key Features

- **🧠 Semantic Embeddings**: Uses state-of-the-art embedding models to understand text meaning.
- **📊 Smart Clustering**: Uses UMAP and KMeans to group semantically similar rows together automatically.
- **🤖 LLM Auto-Naming**: Integrates with the **Groq API** to intelligently generate human-readable names for data clusters.
- **⚡ High-Performance Backend**: Built on FastAPI with asynchronous background task processing.
- **⚛️ Modern Frontend**: A clean, responsive React SPA (Single Page Application) for drag-and-drop file uploads and live progress polling.
- **📁 Automated Exporting**: Generates downloadable ZIP archives containing your cleanly categorized data.

---

## 🏗️ Project Structure

```text
├── app/                  # FastAPI Backend Core
│   ├── api/v1/           # REST API routes (upload, jobs, download)
│   ├── models/           # Pydantic data models
│   ├── services/         # Core logic (embedding, clustering, Groq LLM)
│   └── static/           # Compiled React frontend (served by FastAPI)
├── frontend/             # React + Vite Frontend Source
│   ├── src/              # React components and styling
│   └── package.json      # Node dependencies
├── jobs/                 # Temporary storage for job processing & ZIP exports
├── .env                  # Environment variables (API keys)
└── requirements.txt      # Python dependencies
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** (for frontend development)
- A **Groq API Key** (Get one at [console.groq.com](https://console.groq.com))

### 2. Backend Setup
1. Clone the repository and navigate to the root directory.
2. Copy the example environment file and add your Groq API key:
   ```bash
   cp .env.example .env
   ```
3. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

### 3. Frontend Setup (Development)
The frontend is already built into `app/static` for production, but if you want to make changes:
1. Open a new terminal and navigate to the `frontend/` directory.
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Run the development server (auto-proxies API calls to FastAPI):
   ```bash
   npm run dev
   ```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/health` | Health check endpoint |
| `POST` | `/api/v1/upload` | Upload a CSV/XLSX file and start a classification job |
| `GET`  | `/api/v1/job/{id}` | Poll the current status of a background job |
| `GET`  | `/api/v1/job/{id}/files` | Retrieve the generated manifest and summary metrics |
| `GET`  | `/api/v1/download/{id}` | Download the final exported ZIP file |

---

<div align="center">
  <i>Built with ❤️ using FastAPI, React, and Groq.</i>
</div>
