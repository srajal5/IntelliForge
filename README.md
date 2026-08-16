# AI Intelligence Pipeline

> An end-to-end asynchronous pipeline that crawls AI product data from multiple sources, extracts structured information using LLMs, resolves entities, and stores results in MongoDB with Google Sheets export.

---

## 🎯 Project Purpose

This pipeline automates the discovery, extraction, and organization of AI product intelligence from 5 major verticals (Research Papers, Products, Startups, News Articles, and Tech Jobs). It uses multiple LLM providers (OpenRouter, Gemini, Groq, DeepSeek) with automated fallback for structured data extraction, performs fuzzy entity resolution to deduplicate products and companies, and persists everything in MongoDB with Google Sheets export capabilities.

---

## 🔒 Security & Secrets Management

Security and data privacy are paramount in this repository. All credentials, environment secrets, and private service account keys are strictly managed and guarded against accidental commits to version control.

### 🛡️ Secret File Exclusions (`.gitignore`)
The project `.gitignore` explicitly excludes all sensitive configuration and key files:
- `.env` and `.env.*` (local environment configurations; use `.env.example` as a template)
- `credentials.json`, `token.json`, and `service_account.json` (Google Sheets service account keys)
- `*_credentials.json` and `*secret*.json` (any generic JSON secrets)
- `*.pem`, `*.key`, `*.p12`, `*.crt` (cryptographic certificates and private keys)

### 🔐 Safe Configuration Setup
1. Never commit `.env` or `credentials.json` to Git.
2. Use `.env.example` as the canonical template for environment variable definitions.
3. Service account credentials for Google Sheets should be loaded locally via `GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json` or stored securely as an environment variable (`GOOGLE_SERVICE_ACCOUNT_JSON`).
4. **Snyk Security At Inception**: Standardized static security analysis (`snyk_code_scan`) is performed to ensure **0 security vulnerabilities** across the codebase.

---

## 🏗️ Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Async      │────▶│  LLM         │────▶│  Date /       │
│  Crawlers   │     │  Extraction  │     │  Normalization│
└─────────────┘     └──────────────┘     └───────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Google     │◀────│  MongoDB     │◀────│  Entity       │
│  Sheets     │     │  Storage     │     │  Resolution   │
└─────────────┘     └──────────────┘     └───────────────┘
```

### Module Breakdown

| Module           | Responsibility                                       |
|------------------|------------------------------------------------------|
| `cli/`           | Click-based unified CLI (thin orchestration layer)   |
| `services/`      | Business logic orchestration for each command        |
| `crawlers/`      | Async web crawlers for each data source              |
| `extraction/`    | LLM-based structured field extraction                |
| `normalization/` | Date, pricing, and category normalization            |
| `entity/`        | Fuzzy matching and cross-source entity resolution    |
| `storage/`       | MongoDB persistence via Motor + Checkpoints          |
| `integrations/`  | Google Sheets export and client integration          |
| `models/`        | Pydantic data models for all 5 verticals             |
| `config/`        | Environment-based configuration management           |
| `utils/`         | Structured logging, retry logic, shared helpers      |

---

## 📋 Pipeline Status & Verticals

| Vertical | Source Coverage | Verified MongoDB Records | Target Status |
|---|---|---|---|
| **Research Papers** | ArXiv / GitHub Trending | 1,000 | ✅ 1000+ Complete |
| **Products** | GitHub Multi-Topic Search | 1,069 | ✅ 1000+ Complete |
| **Startups** | Multi-source Registry (GitHub / YC) | 1,008 | ✅ 1000+ Complete |
| **News** | Multi-source RSS (TechCrunch, VentureBeat, etc.) | 1,082 | ✅ 1000+ Complete |
| **Jobs** | Multi-source Job Boards (Arbeitnow, RemoteOK, Jobicy, etc.) | 1,241 | ✅ 1000+ Complete |
| **TOTAL** | **All Ingestion Verticals** | **5,400** | ✅ **100% Target Met** |

---

## 🚀 Setup Instructions

### Prerequisites

- **Python 3.11+**
- **Docker** (for MongoDB)
- **Git**

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-intelligence-pipeline
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables & Secrets

```bash
copy .env.example .env
# Edit .env with your actual API keys and configuration (never commit .env)
```

Place your Google Sheets `credentials.json` at the root directory if enabling Google Sheets export (also protected by `.gitignore`).

### 5. Start MongoDB (via Docker)

```bash
docker-compose up -d
```

### 6. Verify Setup

```bash
python -m src.main health
```

### 7. Run Tests

```bash
pytest
```

---

## 📁 Project Structure

```
ai-intelligence-pipeline/
├── Makefile                  # Make targets (Linux/macOS)
├── README.md
├── requirements.txt
├── .env.example
├── .env                      # Local environment secrets (gitignored)
├── credentials.json          # Google Service Account credentials (gitignored)
├── .gitignore                # Comprehensive secret and build exclusion rules
├── docker-compose.yml
├── scripts/                  # PowerShell wrappers (Windows)
│   ├── test.ps1
│   ├── health.ps1
│   ├── validate.ps1
│   ├── pipeline.ps1
│   └── export.ps1
├── src/
│   ├── __init__.py
│   ├── __main__.py           # python -m src entry point
│   ├── main.py               # python -m src.main entry point
│   ├── cli/                  # Click CLI app & exit codes
│   ├── services/             # Orchestration services for all verticals & export
│   ├── crawlers/             # Multi-source async crawlers
│   ├── extraction/           # LLM extraction & prompt orchestration
│   ├── normalization/        # Normalizers (dates, numbers, text)
│   ├── entity/               # Entity resolution engine & matcher
│   ├── storage/              # Motor repositories & checkpoint store
│   ├── integrations/         # Google Sheets API client & exporters
│   ├── models/               # Pydantic data schemas
│   ├── config/               # Settings & environment parser
│   └── utils/                # Logging, retry, & concurrency helpers
└── tests/                    # 363 automated unit & integration tests
```

---

## 💻 CLI Commands

| Command | Purpose |
|---|---|
| `python -m src.main --help` | Show all available commands |
| `python -m src.main health` | Check system configuration and connectivity |
| `python -m src.main test` | Run automated tests |
| `python -m src.main stats` | Show database statistics |
| `python -m src.main validate` | Run data-quality validation |
| `python -m src.main pipeline --limit 10` | Run end-to-end pipeline (safe default) |
| `python -m src.main research --limit 1000` | Ingest research papers |
| `python -m src.main startups --limit 1000` | Ingest startups |
| `python -m src.main products --limit 1000` | Ingest products |
| `python -m src.main news --limit 1000` | Ingest news articles |
| `python -m src.main jobs --limit 1000` | Ingest tech jobs |
| `python -m src.main resolve` | Run fuzzy entity resolution |
| `python -m src.main export` | Export MongoDB dataset to Google Sheets |
| `python -m src.main benchmark --records 1000` | Run performance benchmark |

### Windows PowerShell Shortcuts

```powershell
.\scripts\test.ps1
.\scripts\health.ps1
.\scripts\validate.ps1
.\scripts\pipeline.ps1 -Limit 10
.\scripts\export.ps1
```

### Exit Codes

| Code | Meaning |
|------|---|
| 0 | Success |
| 1 | General failure |
| 2 | Invalid CLI arguments |
| 3 | Configuration failure |
| 4 | Validation failure |
| 5 | Infrastructure/service failure |

---

## 📄 License

This project is part of an AI Engineer assessment.

