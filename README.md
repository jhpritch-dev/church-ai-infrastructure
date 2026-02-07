# Episcopal Bulletin Generator

AI-powered church bulletin generation system for Episcopal churches. Automates liturgical content management, scripture reading selection via the Revised Common Lectionary, and integration with the Book of Common Prayer (1979).

## Architecture

```
Browser (localhost)
    │
    ├── Flask Dashboard (:5000)     ← User-facing web GUI
    │       │
    │       ▼
    ├── FastAPI Backend (:8001)     ← Bulletin generation API
    │       ├── Hymn Lookup (Hymnal 1982)
    │       ├── DOCX Generator (BCP-style formatting)
    │       └── [Future: RCL readings, Ollama AI]
    │
    ├── PostgreSQL (:5432)          ← Data persistence
    ├── Redis (:6379)               ← Caching / task queue
    ├── Ollama (:11434)             ← Local LLM (llama3.1:8b)
    ├── Paperless-NGX (:8080)       ← Document management / OCR
    ├── Open Notebook (:3030)       ← Document chat
    └── SurrealDB (:8000)           ← Notebook storage
```

## Phase 1 Features

- **DOCX Bulletin Generation** — BCP Rite II formatted bulletins with Garamond typography, proper liturgical sections, half-letter page size
- **Hymnal 1982 Lookup** — 55+ hymns indexed by number with title, tune, composer, and liturgical season
- **Web Dashboard** — Flask-based GUI for generating and downloading bulletins
- **API with Swagger Docs** — Full REST API at `/docs` for programmatic access
- **Offline-First** — All processing runs locally via Docker; no cloud dependencies
- **Docker Compose Stack** — 8 services, 48GB RAM allocation with 16GB Windows reserve

## Quick Start

### Prerequisites
- Windows 11 Pro with Docker Desktop
- 64GB RAM recommended (48GB allocated to Docker)
- Python 3.12+ (for local development)

### Deploy with Docker

```powershell
cd D:\Docker

# 1. Copy bulletin-backend/ and flask-web-gui/ to D:\Docker\
# 2. Copy docker-compose.yml to D:\Docker\

# 3. Build and start
docker compose build bulletin-api flask-web-gui
docker compose up -d

# 4. Access
# Dashboard:    http://localhost:5000
# API Docs:     http://localhost:8001/docs
# Generate:     http://localhost:8001/form
# Hymn Lookup:  http://localhost:8001/hymn/390
```

### Local Development (no Docker)

```powershell
cd D:\Docker\bulletin-backend
python -m pip install -r requirements.txt

# Start API on port 8001 (avoids SurrealDB on 8000)
python -m uvicorn app:app --host 0.0.0.0 --port 8001

# Test
# http://localhost:8001/health
# http://localhost:8001/form
# http://localhost:8001/hymn/390
```

### Automated Setup

```powershell
.\deploy-phase1.ps1              # Full deploy
.\deploy-phase1.ps1 -LocalTest   # Test without Docker
.\deploy-phase1.ps1 -SkipBuild   # Skip image build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/form` | HTML bulletin form |
| POST | `/generate` | Generate DOCX bulletin |
| GET | `/bulletins` | List generated bulletins |
| GET | `/output/{filename}` | Download bulletin |
| GET | `/hymn/{number}` | Hymn lookup |

## Project Structure

```
D:\Docker\
├── docker-compose.yml
├── deploy-phase1.ps1
├── bulletin-backend/           # FastAPI bulletin generation API
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── hymn_lookup.py      # Hymnal 1982 database + lookup
│   │   └── docx_generator.py   # BCP-style DOCX generation
│   └── data/
│       └── hymnal_1982.json    # 55+ hymns indexed by number
├── flask-web-gui/              # Flask web dashboard
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/
│       └── index.html
└── [existing services...]
    ├── ollama/
    ├── postgres/
    ├── redis/
    ├── paperless/
    ├── surrealdb/
    └── open-notebook/
```

## Resource Allocation (48GB)

| Service | Limit | Reserved | Notes |
|---------|-------|----------|-------|
| Ollama | 24GB | 16GB | llama3.1:8b + headroom |
| PostgreSQL | 6GB | 3GB | Tuned for SSD |
| Paperless-NGX | 6GB | 3GB | OCR + 4 workers |
| Open Notebook | 2GB | 1GB | Document chat |
| Bulletin API | 2GB | 1GB | FastAPI backend |
| Redis | 1GB | 512MB | Cache/queue |
| SurrealDB | 1GB | 512MB | Notebook storage |
| Flask GUI | 1GB | 512MB | Web dashboard |
| **Total** | **43GB** | **25.5GB** | **16GB+ Windows headroom** |

## Roadmap

- [ ] **Phase 2**: Vertical slice bulletin generator with RCL readings + collects
- [ ] **Phase 3**: Anthem/music selection with AI recommendations
- [ ] **Phase 4**: PDF asset extraction from existing bulletins
- [ ] **Phase 5**: Distribution (Electron app / Docker Desktop bundle / PWA)

## Tech Stack

- **Backend**: FastAPI, python-docx, Pydantic
- **Frontend**: Flask, Jinja2
- **AI**: Ollama (llama3.1:8b), local inference
- **Data**: PostgreSQL 16, Redis 7, SurrealDB
- **Documents**: Paperless-NGX (OCR), Open Notebook
- **Infrastructure**: Docker Compose, Windows 11 Pro

## License

Private project — Episcopal bulletin generation system for church operations automation.
