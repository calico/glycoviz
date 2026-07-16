# GlycoViz #

Glycan analysis application with build-in glycan validation algorithm  using React + FastAPI + PostgreSQL.
![img.png](img.png)

# User Guide #
Please find the user guide under the root folder. 

## Architecture

- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS + react-plotly.js
- **Backend:** FastAPI + Python 3.11+ + SQLAlchemy + Alembic
- **Database:** PostgreSQL
- **Charts:** Plotly (via react-plotly.js)

## Quick Start

### With Docker Compose

```bash
docker-compose up
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/docs
- PostgreSQL: localhost:5432

### Manual Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Running Tests

```bash
cd backend
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Run only unit tests
python -m pytest tests/test_statistics.py tests/test_glycan_lookup.py tests/test_glycan_validator.py tests/test_foldchange.py -v

# Run only API/integration tests
python -m pytest tests/test_api/ -v
```

## API Documentation

The backend exposes a REST API that powers all frontend functionality. Any operation available in the UI can also be performed programmatically via HTTP requests.

Interactive API documentation is available when the backend is running:

- **With Docker Compose:** http://localhost:5173/api/docs or http://localhost:8000/docs, depending on proxy settings
- **Manual development:** http://localhost:8000/docs (Swagger UI) or http://localhost:8000/redoc

## Project Structure

```
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── api/      # Route handlers
│   │   ├── core/     # Algorithm modules (glycan converter, clustering, etc.)
│   │   ├── db/       # Database session & migrations
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── schemas/  # Pydantic request/response schemas
│   │   └── services/ # Business logic
│   └── tests/
│   └── example_data/  # Sample input files (Byonic, MSFragger, etc.)
├── frontend/         # React + TypeScript application
│   └── src/
│       ├── api/       # API client
│       ├── components/ # Reusable UI components
│       ├── pages/     # Route-level pages
│       ├── hooks/     # Custom React hooks
│       └── types/     # TypeScript type definitions
└── docker-compose.yml
```
