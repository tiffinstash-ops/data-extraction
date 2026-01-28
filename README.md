
# Tiffinstash Data Extraction & Management

This repository is divided into two main services:

## 1. Backend (FastAPI)
Located in `/backend`.
Handles Shopify API integration, data transformations, and PostgreSQL database interactions via Cloud SQL.

### Features:
- Shopify Order Fetching
- Post-edit & Master Data Transformations
- Delivery Management API (CRUD on Postgres)
- Seller Information API

### Deployment:
- Dockerfile: `/backend/Dockerfile`
- Port: 8000

## 2. Frontend (Streamlit)
Located in `/frontend`.
Provides the user interface for fetching orders, viewing statistics, and managing deliveries.

### Features:
- Dashboard for order fetching and processing.
- Delivery Management dashboard with a form to update SKU fields and TL Notes.
- Dynamic Seller Dashboards.

### Deployment:
- Dockerfile: `/frontend/Dockerfile`
- Port: 8501
- Environment Variables: `BACKEND_URL` (default: http://localhost:8000)

## Getting Started

### Local Development
1. Start Backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   export PYTHONPATH=$PYTHONPATH:.
   uvicorn app.main:app --reload
   ```

2. Start Frontend:
   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run app/main.py
   ```

### Docker Compose (Recommended)
You can use Docker Compose to run both services together.

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/data:/app/data
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

  frontend:
    build: ./frontend
    ports:
      - "8501:8501"
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      - backend
```
