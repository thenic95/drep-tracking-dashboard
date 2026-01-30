# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cardano DRep (Delegated Representative) Tracking Dashboard - an MVP web application that displays governance voting behavior and activity status of Cardano DReps. Fetches real-time data from the Koios blockchain API.

## Development Commands

### Backend (FastAPI + Python)

```bash
# Setup (from project root)
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initial database population (run once, from project root)
python -m backend.main_data_loader

# Run development server (from project root)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests (from project root)
pytest backend/tests/

# Run a single test
pytest backend/tests/test_api.py::test_get_tracked_dreps -v
```

### Frontend (Vue 3 + Vite)

```bash
cd frontend/frontend-app
npm install
npm run dev      # Development server at http://localhost:5173
npm run build    # Production build
npm run preview  # Preview production build
```

## Architecture

### Data Flow

```
Vue Frontend (localhost:5173)
    ↓ Vite proxy (/api → localhost:8000)
FastAPI Backend (localhost:8000)
    ↓
SQLite Database (backend/drep_tracker.db)
    ↓ Background scheduler (hourly/6-hourly updates)
Koios API (api.koios.rest)
```

### Backend Structure (`backend/`)

- `main.py` - FastAPI application entry point, mounts Panel dashboard at `/dashboard`
- `koios_api.py` - Koios blockchain API client with retry logic
- `data_manager.py` - Core data processing and sync logic
- `database.py` / `database_setup.py` - SQLite operations and schema
- `scheduler.py` - Background job scheduler (runs in separate thread)
- `config.py` - Configuration constants and API tokens
- `schemas.py` - Pydantic models for API responses

### Frontend Structure (`frontend/frontend-app/src/`)

- `views/DashboardView.vue` - Main dashboard container
- `components/DRepTable.vue` - DRep listing with column-based filtering
- `components/GovernanceActionMatrix.vue` - Voting matrix visualization
- `components/DRepManagement.vue` - Add/remove tracked DReps
- `services/apiService.js` - Axios HTTP client for backend API

### Database Tables

- `dreps` - DRep profiles (voting power, delegators, activity status)
- `governance_actions` - Governance proposals
- `drep_votes` - Voting records (drep_id, ga_id, vote)
- `tracked_dreps` - User's watched DReps list

### API Endpoints

- `GET /api/dreps/tracked` - List tracked DReps
- `POST /api/dreps/tracked/{drep_id}` - Add DRep to tracking
- `DELETE /api/dreps/tracked/{drep_id}` - Remove DRep from tracking
- `GET /api/governance-actions` - List governance actions (supports pagination: limit, offset)
- `GET /api/governance-actions/{ga_id}/votes` - Get votes for a specific GA

## Key Configuration

- Koios API token in `backend/config.py` (KOIOS_API_TOKEN)
- Initial DReps to track in `backend/config.py` (INITIAL_DREP_LIST)
- Vite proxy configuration in `frontend/frontend-app/vite.config.js`

## Background Scheduler

Runs automatically on FastAPI startup:
- DRep on-chain info updates: every 1 hour
- DRep metadata checks: every 6 hours
- Governance actions & votes: every 2 hours
