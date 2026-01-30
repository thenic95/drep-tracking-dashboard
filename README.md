# Cardano DRep Tracking Dashboard

## Overview

The Cardano DRep Tracking Dashboard is a web application designed to transparently display key information and voting behavior of selected Cardano Delegated Representatives (DReps). This Minimum Viable Product (MVP) is intended for local execution and provides insights into DRep activities and governance participation.

## Features (MVP)

*   **DRep Profile & Status Overview:** Displays DRep ID, Name (when available from metadata), registration epoch and date, current voting power, number of delegators, and activity status (Active, Inactive, Expired).
*   **Governance Action (GA) Vote Tracking:** Lists governance actions with details (title, type, submission/expiration epochs). For tracked DReps, it shows their vote on each GA (Yes, No, Abstain, Did Not Vote) with visual cues. Handles cases where a DRep might not have been registered at the time of a GA.
*   **Simplified DRep List Management:** Users can add or remove DRep IDs from a tracked list via the API, and the dashboard will dynamically update to reflect these changes.
*   **Column Filtering:** The DRep table now includes filter inputs for each column, allowing quick searching and narrowing of results.
*   **Data Sourced from Koios API:** All on-chain DRep and governance data is fetched from the Koios API.
*   **Automatic Data Updates:** A backend scheduler periodically fetches the latest on-chain data to keep the dashboard updated. This includes DRep on-chain status, off-chain metadata verification, and new governance actions/votes.

## Tech Stack

*   **Backend:**
    *   Python 3.10+
    *   FastAPI (for the REST API)
    *   Uvicorn (ASGI server)
    *   SQLite (for local data storage)
    *   `requests` (for Koios API communication)
    *   `schedule` (for background data update tasks)
*   **Frontend:**
    *   Vue.js 3 (with Vite)
    *   `axios` (for API communication with the backend)
    *   HTML, CSS, JavaScript
*   **Data Source:**
    *   [Koios API](https://api.koios.rest/)

## Project Structure

```
.
├── backend/
│   ├── __init__.py
│   ├── config.py           # Configuration (API keys, DRep list, DB path)
│   ├── data_manager.py     # Core logic for fetching & processing data
│   ├── database.py         # Database interaction functions
│   ├── database_setup.py   # Script to initialize DB schema
│   ├── drep_tracker.db     # SQLite database file (created on run)
│   ├── koios_api.py        # Koios API client functions
│   ├── main.py             # FastAPI application
│   ├── requirements.txt    # Backend Python dependencies
│   ├── scheduler.py        # Background task scheduler
│   └── schemas.py          # Pydantic schemas for API
├── frontend/
│   └── frontend-app/       # Vue.js project
│       ├── public/
│       ├── src/
│       │   ├── assets/         # CSS, images
│       │   ├── components/     # Vue components (DRepTable, GovernanceActionMatrix, etc.)
│       │   ├── services/       # apiService.js
│       │   ├── views/          # Vue views (DashboardView)
│       │   ├── App.vue         # Main Vue application component
│       │   └── main.js         # Vue app initialization
│       ├── index.html
│       ├── package.json
│       └── vite.config.js      # Vite configuration (including proxy)
└── README.md                   # This file
```

## Prerequisites

*   Python (version 3.10+ recommended)
*   Node.js (version 16+ recommended, which includes npm)
*   `git` for cloning the repository
*   `sqlite3` command-line tool (for manual DB inspection, often pre-installed with Python or easily installable)
*   `curl` and `jq` (for testing API endpoints via command line)

## Setup and Installation

**Note:** Unless specified otherwise, all commands should be run from the project root directory (the directory containing the `backend` and `frontend` folders).

### Quick Start

Follow these steps to run the dashboard locally:

1. **Clone the repository** and move into it:

   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Set up and start the backend** in one terminal:

   ```bash
   cd backend
   python -m venv venv
   # Activate the virtual environment
   source venv/bin/activate     # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt  # installs bokeh-fastapi and hvplot
   # If installing Panel separately, ensure `panel[fastapi]` or `bokeh-fastapi` is present
   cd ..
   # Populate the SQLite database
   python -m backend.main_data_loader
   # Start the FastAPI server
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   The backend API will be available at `http://localhost:8000` and the
   dashboard at `http://localhost:8000/dashboard`.

3. **Start the frontend** in a second terminal:

   ```bash
   cd frontend/frontend-app
   npm install
   npm run dev
   ```

   Visit `http://localhost:5173` to view the dashboard UI.

Detailed setup instructions are provided below.

### 1. Clone the Repository

```bash
git clone <repository_url>
cd <repository_directory>
```

### 2. Backend Setup

a.  **Create and Activate Virtual Environment:**
    Navigate to the backend directory and create/activate a virtual environment.
    ```bash
    cd backend
    python -m venv venv
    ```
    Activate the virtual environment:
    *   Windows: `venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`
    
    Return to the project root directory:
    ```bash
    cd ..
    ```

b.  **Install Dependencies:**
    Install the required Python packages from within the project root, ensuring the backend virtual environment is active.
    ```bash
    # Ensure backend virtual environment is active (e.g., (venv) prefix in terminal)
    pip install -r backend/requirements.txt  # bokeh-fastapi & hvplot included
    ```

c.  **Database Initialization & Initial Data Load (Recommended First Step):**
    The backend uses an SQLite database (`backend/drep_tracker.db`). For the first time, it's highly recommended to initialize and populate the database by running the `main_data_loader.py` script. This will create the necessary tables and perform an initial data load.

    ```bash
    # Ensure your backend virtual environment is activated (see step 2a)
    # From the project root directory:
    python -m backend.main_data_loader 
    ```
    This script populates the database with initial DReps (from `config.py`), fetches details for governance actions, and retrieves votes for all available proposals (unless configured otherwise in `backend/config.py`). After this, the backend server can be started.

### 3. Frontend Setup

Navigate to the frontend directory and install npm packages.
```bash
cd frontend/frontend-app 
npm install
```
Return to the project root directory if you wish, or keep this terminal for running the frontend server.
```bash
cd ../.. 
```

## Running the Application

You will typically have two terminals running concurrently: one for the backend server and one for the frontend development server.

1.  **Start the Backend Server:**
    *   Open a terminal in the project root directory.
    *   Ensure your backend virtual environment is activated:
        *   Windows: `backend\venv\Scripts\activate`
        *   macOS/Linux: `source backend/venv/bin/activate`
    *   Run Uvicorn:
        ```bash
        # From the project root directory
        uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
        ```
    *   The backend API will be available at `http://localhost:8000`.
    *   The dashboard is served at `http://localhost:8000/dashboard`.
    *   The scheduler for data updates will start in a background thread. Logs will indicate job scheduling and execution.

2.  **Start the Frontend Development Server:**
    *   Open another terminal in the project root directory.
    *   Navigate to the frontend application directory: 
        ```bash
        cd frontend/frontend-app
        ```
    *   Run the Vite development server:
        ```bash
        npm run dev
        ```
    *   The frontend application will be accessible at `http://localhost:5173` (or another port if 5173 is busy - check Vite output). The Vite dev server is configured to proxy API requests from `/api` to the backend at `http://localhost:8000`.

## Koios API Token

The application uses a Koios API token.

1.  **Get a Token:** Sign up at [Koios](https://koios.rest/) to get a free tier token.
2.  **Configure Environment:**
    *   Navigate to the `backend` directory.
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
        (Or manually create `.env` and add `KOIOS_API_TOKEN=your_token_here`)
    *   Paste your API token into the `.env` file.

## Data Updates

The backend includes an automated scheduler that periodically performs the following tasks:
*   **DRep On-Chain Info Update:** (e.g., voting power, delegator count, activity status) - Default: Every 1 hour.
*   **DRep Off-Chain Metadata Update:** (e.g., fetches DRep metadata from their `metadata_url` and verifies hash) - Default: Every 6 hours.
*   **Recent Governance Actions & Votes Update:** Fetches new governance actions and updates votes for recent/active ones - Default: Every 2 hours.

These schedules are defined in `backend/scheduler.py` and can be adjusted. The scheduler starts automatically when the backend FastAPI application starts. Jobs are also run once on startup for immediate data availability.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

