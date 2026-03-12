import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import (
    cf_delegation,
    config,  # For LOG_LEVEL, potentially other API configs
    data_manager,
    database,
    scheduler,  # Assuming scheduler.py is in the same directory (backend)
    schemas,
)

try:
    from panel.io.fastapi import mount_panel
except Exception as e:  # pragma: no cover - handle missing deps or older Panel
    try:
        from panel.io.fastapi import add_applications

        def mount_panel(app, path, view):
            add_applications({path: view}, app=app)

    except Exception:
        logging.getLogger(__name__).warning(
            "Panel FastAPI integration unavailable (%s); dashboard will not be mounted",
            e,
        )

        def mount_panel(app, path, view):
            logging.getLogger(__name__).warning(
                "Skipping Panel dashboard mount due to missing dependencies"
            )
            return


from .dashboard import dashboard

# Configure logging
logger = logging.getLogger(__name__)  # Use __name__ for module-level logger
# The root logger will be configured by Uvicorn or the if __name__ == "__main__": block.
# Set level for this specific logger if needed, or rely on root logger's level.
logger.setLevel(config.LOG_LEVEL)
# Add a handler if running this module directly and it's not getting configured by an entry point.
if not logger.handlers and not logging.getLogger().handlers:
    # This basicConfig is a fallback if no other logging is configured.
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )




# Initialize FastAPI app
app = FastAPI(title="DRep Tracker API", version="0.1.0")
mount_panel(app, "/dashboard", dashboard)

# --- Scheduler Startup ---
_scheduler_thread = None


async def _retry_failed_metadata():
    """On startup, re-attempt metadata fetch for all tracked DReps (covers previously failed ones)."""
    db = database.get_db_connection()
    try:
        await data_manager.update_drep_offchain_metadata_for_tracked(db)
    except Exception as e:
        logger.error(f"Error in startup metadata retry: {e}", exc_info=True)
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    global _scheduler_thread
    # Ensure database tables are created before starting scheduler or API.
    # This is important if the scheduler runs a job immediately that needs the DB.
    logger.info("Application startup: Ensuring database tables are created.")
    print("FastAPI Startup: Ensuring database tables are created.")
    try:
        database.create_tables_if_not_exist()
        logger.info("Database tables verified/created successfully for startup.")
        print("Database tables verified/created successfully for startup.")
    except Exception as e:
        logger.error(
            f"Critical error during database setup on startup: {e}", exc_info=True
        )
        print(f"Critical error during database setup on startup: {e}")
        # Depending on severity, you might want to prevent app startup.
        # For now, log and continue, but scheduler/API might fail.

    if not (_scheduler_thread and _scheduler_thread.is_alive()):
        logger.info("Starting scheduler in a background thread...")
        print("FastAPI Startup: Attempting to start scheduler thread...")
        # Using the start_scheduler_thread function from scheduler.py
        # which itself creates and starts the thread.
        scheduler.start_scheduler_thread()
        logger.info(
            "Scheduler thread has been initiated via scheduler.start_scheduler_thread()."
        )
        print(
            "FastAPI Startup: Scheduler thread initiation attempted via scheduler.start_scheduler_thread()."
        )
    else:
        logger.info("Scheduler thread already running.")
        print("FastAPI Startup: Scheduler thread already running.")

    asyncio.create_task(_retry_failed_metadata())


# CORS Middleware
# Allows all origins for now, can be restricted in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Database Dependency ---
# def get_db():
#     """FastAPI dependency to get a database connection."""
#     try:
#         # database.create_tables_if_not_exist() # Moved to app startup
#         db = database.get_db_connection()
#         yield db
#     except sqlite3.Error as e: # More specific exception for DB errors
#         logger.error(f"Database connection or operational error: {e}", exc_info=True)
#         raise HTTPException(status_code=503, detail="Database service unavailable.")
#     except Exception as e:
#         logger.error(f"Unexpected error in get_db dependency: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error establishing database connection.")
#     finally:
#         if 'db' in locals() and db is not None:
#             try:
#                 db.close()
#                 logger.debug("Database connection closed by get_db dependency.")
#             except Exception as e:
#                 logger.error(f"Error closing DB connection in get_db: {e}", exc_info=True)


def get_db_dep():
    """
    FastAPI dependency that provides a SQLAlchemy Session.
    Ensures the session is closed after the request is processed.
    """
    db = database.get_db_connection()
    try:
        yield db
    finally:
        db.close()


# --- API Endpoints ---


# -- DReps Endpoints --
@app.get("/api/dreps/tracked", response_model=List[schemas.DRep])
def get_tracked_dreps_details(db: sqlite3.Connection = Depends(get_db_dep)):
    """Returns details of all DReps in the tracked_dreps list."""
    logger.info("Endpoint GET /api/dreps/tracked hit")
    try:
        dreps_data = database.get_all_tracked_drep_details(db)
        if not dreps_data:
            logger.info("No tracked DReps found.")
            return []
        return dreps_data
    except Exception as e:
        logger.error(f"Error in /api/dreps/tracked: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing request for tracked DReps.",
        ) from e


@app.get("/api/dreps/{drep_id}", response_model=schemas.DRep)
def get_drep_by_id_endpoint(drep_id: str, db: sqlite3.Connection = Depends(get_db_dep)):
    """Returns details for a specific DRep ID."""
    logger.info(f"Endpoint GET /api/dreps/{drep_id} hit")
    try:
        drep_data = database.get_drep_by_id(db, drep_id)
        if drep_data is None:
            logger.warning(f"DRep with ID {drep_id} not found.")
            raise HTTPException(
                status_code=404, detail=f"DRep with ID {drep_id} not found"
            )
        return drep_data
    except (
        HTTPException
    ):  # Re-raise HTTPException to avoid being caught by generic Exception
        raise
    except Exception as e:
        logger.error(f"Error in /api/dreps/{drep_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing request for DRep {drep_id}.",
        ) from e


@app.post(
    "/api/dreps/tracked/{drep_id}", response_model=schemas.TrackedDRep, status_code=201
)
def add_drep_to_tracked_list(
    drep_id: str, db: sqlite3.Connection = Depends(get_db_dep)
):
    """Adds a DRep ID to the tracked_dreps table."""
    logger.info(f"Endpoint POST /api/dreps/tracked/{drep_id} hit")
    try:
        # Check if DRep exists in 'dreps' table, add minimal if not (database.add_tracked_drep handles this)
        database.add_tracked_drep(db, drep_id)
        logger.info(f"DRep {drep_id} added to tracked list (or already present).")
        return schemas.TrackedDRep(drep_id=drep_id)
    except (
        Exception
    ) as e:  # Catch specific DB errors if possible, e.g. IntegrityError for FK
        logger.error(f"Error adding DRep {drep_id} to tracked list: {e}", exc_info=True)
        # Consider if this should be a 400 if drep_id format is invalid, or 500 for DB issues.
        raise HTTPException(
            status_code=500, detail=f"Failed to add DRep {drep_id} to tracked list."
        ) from e


@app.delete("/api/dreps/tracked/{drep_id}", status_code=204)
def remove_drep_from_tracked_list(
    drep_id: str, db: sqlite3.Connection = Depends(get_db_dep)
):
    """Removes a DRep ID from the tracked_dreps table."""
    logger.info(f"Endpoint DELETE /api/dreps/tracked/{drep_id} hit")
    try:
        # Check if DRep is currently tracked to provide more specific feedback (optional)
        tracked_ids = database.get_tracked_drep_ids(db)
        if drep_id not in tracked_ids:
            logger.warning(
                f"Attempted to delete DRep {drep_id} from tracked list, but it was not found."
            )
            # Returning 204 is idempotent, so even if not found, it's "gone".
            # Alternatively, raise HTTPException(status_code=404, detail=f"DRep {drep_id} not found in tracked list.")
            return  # No content, as it's effectively removed or was never there.

        database.remove_tracked_drep(db, drep_id)
        logger.info(f"DRep {drep_id} removed from tracked list.")
        return  # FastAPI will return 204 No Content automatically
    except Exception as e:
        logger.error(
            f"Error removing DRep {drep_id} from tracked list: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove DRep {drep_id} from tracked list.",
        ) from e


# -- Voting Power History Endpoint --
@app.get(
    "/api/dreps/{drep_id}/voting-power-history",
    response_model=List[schemas.VotingPowerSnapshot],
)
def get_voting_power_history_endpoint(
    drep_id: str,
    db: sqlite3.Connection = Depends(get_db_dep),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Returns voting power snapshots for a specific DRep, ordered by epoch descending."""
    logger.info(
        f"Endpoint GET /api/dreps/{drep_id}/voting-power-history hit with limit={limit}, offset={offset}"
    )
    try:
        drep_exists = database.get_drep_by_id(db, drep_id)
        if not drep_exists:
            raise HTTPException(
                status_code=404, detail=f"DRep with ID {drep_id} not found."
            )
        snapshots = database.get_voting_power_history(
            db, drep_id, limit=limit, offset=offset
        )
        return snapshots
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in /api/dreps/{drep_id}/voting-power-history: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing voting power history for DRep {drep_id}.",
        ) from e


# -- Governance Actions Endpoints --
@app.get("/api/governance-actions", response_model=List[schemas.GovernanceAction])
def get_governance_actions_endpoint(
    db: sqlite3.Connection = Depends(get_db_dep),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Returns all governance actions with pagination."""
    logger.info(
        f"Endpoint GET /api/governance-actions hit with limit={limit}, offset={offset}"
    )
    try:
        ga_data = database.get_all_governance_actions(db, limit=limit, offset=offset)
        if not ga_data:
            logger.info("No governance actions found for the given pagination.")
            # Return empty list, not an error, as per typical API behavior for empty collections
            return []
        return ga_data
    except Exception as e:
        logger.error(f"Error in /api/governance-actions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing request for governance actions.",
        ) from e


# -- Vote Matrix Endpoint --
# NOTE: This must be defined BEFORE the parameterized {ga_id} route below,
# otherwise FastAPI matches "vote-matrix" as a {ga_id} value.
@app.get("/api/governance-actions/vote-matrix", response_model=schemas.VoteMatrixResponse)
def get_vote_matrix(
    db: sqlite3.Connection = Depends(get_db_dep),
    ga_limit: int = Query(20, ge=1, le=200),
    ga_offset: int = Query(0, ge=0),
):
    """Returns governance actions with votes pre-filtered to tracked DReps only."""
    logger.info(
        f"Endpoint GET /api/governance-actions/vote-matrix hit with ga_limit={ga_limit}, ga_offset={ga_offset}"
    )
    try:
        tracked_drep_ids = database.get_tracked_drep_ids(db)
        gas = database.get_all_governance_actions(db, limit=ga_limit, offset=ga_offset)

        result_gas = []
        for ga in gas:
            votes = database.get_votes_for_ga_by_dreps(db, ga["ga_id"], tracked_drep_ids)
            drep_votes = {v["drep_id"]: v["vote"] for v in votes}
            result_gas.append({**ga, "drep_votes": drep_votes})

        # Get total count for pagination
        all_ga_ids = database.get_all_ga_ids(db)
        return {"governance_actions": result_gas, "total_count": len(all_ga_ids)}
    except Exception as e:
        logger.error(f"Error in /api/governance-actions/vote-matrix: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing vote matrix.",
        ) from e


@app.get("/api/governance-actions/{ga_id}/votes", response_model=List[schemas.DRepVote])
def get_votes_for_governance_action(
    ga_id: str,
    db: sqlite3.Connection = Depends(get_db_dep),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Returns all votes for a specific GA ID with pagination."""
    logger.info(
        f"Endpoint GET /api/governance-actions/{ga_id}/votes hit with limit={limit}, offset={offset}"
    )
    try:
        # First, check if the GA exists
        ga_exists = database.get_ga_by_id(db, ga_id)
        if not ga_exists:
            logger.warning(f"Governance action with ID {ga_id} not found.")
            raise HTTPException(
                status_code=404, detail=f"Governance action with ID {ga_id} not found."
            )

        votes_data = database.get_votes_for_ga(db, ga_id, limit=limit, offset=offset)
        if not votes_data:
            logger.info(f"No votes found for GA ID {ga_id} with the given pagination.")
            return []  # Return empty list if no votes, not an error
        return votes_data
    except HTTPException:  # Re-raise HTTPException
        raise
    except Exception as e:
        logger.error(
            f"Error in /api/governance-actions/{ga_id}/votes: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing votes for GA {ga_id}.",
        ) from e


# -- Optional DRep Votes Endpoint --
@app.get("/api/dreps/{drep_id}/votes", response_model=List[schemas.DRepVote])
def get_votes_by_drep_endpoint(
    drep_id: str,
    db: sqlite3.Connection = Depends(get_db_dep),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Returns all votes cast by a specific DRep with pagination."""
    logger.info(
        f"Endpoint GET /api/dreps/{drep_id}/votes hit with limit={limit}, offset={offset}"
    )
    try:
        # First, check if the DRep exists
        drep_exists = database.get_drep_by_id(db, drep_id)
        if not drep_exists:
            logger.warning(
                f"DRep with ID {drep_id} not found when trying to fetch votes."
            )
            raise HTTPException(
                status_code=404, detail=f"DRep with ID {drep_id} not found."
            )

        votes_data = database.get_votes_by_drep(db, drep_id, limit=limit, offset=offset)
        if not votes_data:
            logger.info(
                f"No votes found for DRep ID {drep_id} with the given pagination."
            )
            return []
        return votes_data
    except HTTPException:  # Re-raise HTTPException
        raise
    except Exception as e:
        logger.error(f"Error in /api/dreps/{drep_id}/votes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing votes for DRep {drep_id}.",
        ) from e


# -- CF Delegation Endpoints --
@app.get("/api/cf-delegation/dreps", response_model=List[schemas.CFDelegationDRepResponse])
def get_cf_delegation_dreps(db: sqlite3.Connection = Depends(get_db_dep)):
    """Returns CF-delegated DReps with computed metrics."""
    logger.info("Endpoint GET /api/cf-delegation/dreps hit")
    try:
        current_epoch = None
        try:
            current_epoch = asyncio.run(data_manager.get_current_epoch())
        except Exception:
            pass

        if current_epoch is None:
            current_epoch = 0

        thresholds = cf_delegation.get_thresholds(db)
        dreps = database.get_cf_delegated_dreps(db)

        result = []
        for drep_data in dreps:
            metrics = cf_delegation.compute_drep_metrics(
                db, drep_data, current_epoch, thresholds
            )
            result.append({**drep_data, **metrics})
        return result
    except Exception as e:
        logger.error(f"Error in /api/cf-delegation/dreps: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing CF delegation DReps.",
        ) from e


@app.put("/api/cf-delegation/dreps/{drep_id}/delegation-date")
def update_delegation_date(
    drep_id: str,
    body: schemas.DelegationDateUpdate,
    db: sqlite3.Connection = Depends(get_db_dep),
):
    """Sets the user-defined delegation date for a DRep (used to calculate tenure)."""
    logger.info(f"Endpoint PUT /api/cf-delegation/dreps/{drep_id}/delegation-date hit")
    drep = database.get_drep_by_id(db, drep_id)
    if not drep:
        raise HTTPException(status_code=404, detail=f"DRep {drep_id} not found.")
    database.update_drep_delegation_date(db, drep_id, body.delegation_date)
    return {"drep_id": drep_id, "delegation_date": body.delegation_date}


@app.put("/api/cf-delegation/dreps/{drep_id}/alignment-score")
def update_alignment_score(
    drep_id: str,
    body: schemas.AlignmentScoreUpdate,
    db: sqlite3.Connection = Depends(get_db_dep),
):
    """Updates the alignment score for a DRep."""
    logger.info(f"Endpoint PUT /api/cf-delegation/dreps/{drep_id}/alignment-score hit")
    drep = database.get_drep_by_id(db, drep_id)
    if not drep:
        raise HTTPException(status_code=404, detail=f"DRep {drep_id} not found.")
    database.update_drep_alignment_score(db, drep_id, body.score)
    return {"drep_id": drep_id, "alignment_score": body.score}


@app.put("/api/cf-delegation/dreps/{drep_id}/delegation")
def update_cf_delegation(
    drep_id: str,
    body: schemas.CFDelegationUpdate,
    db: sqlite3.Connection = Depends(get_db_dep),
):
    """Manual override for CF delegation epoch and amount."""
    logger.info(f"Endpoint PUT /api/cf-delegation/dreps/{drep_id}/delegation hit")
    drep = database.get_drep_by_id(db, drep_id)
    if not drep:
        raise HTTPException(status_code=404, detail=f"DRep {drep_id} not found.")
    database.update_drep_cf_delegation(
        db, drep_id, body.cf_delegated_ada, body.delegation_epoch
    )
    return {
        "drep_id": drep_id,
        "delegation_epoch": body.delegation_epoch,
        "cf_delegated_ada": body.cf_delegated_ada,
    }


@app.get("/api/cf-delegation/thresholds", response_model=schemas.CFThresholdSettings)
def get_cf_thresholds(db: sqlite3.Connection = Depends(get_db_dep)):
    """Returns current CF delegation threshold settings."""
    return cf_delegation.get_thresholds(db)


@app.put("/api/cf-delegation/thresholds", response_model=schemas.CFThresholdSettings)
def update_cf_thresholds(
    body: schemas.CFThresholdSettings,
    db: sqlite3.Connection = Depends(get_db_dep),
):
    """Updates CF delegation threshold settings."""
    logger.info("Endpoint PUT /api/cf-delegation/thresholds hit")
    for key, value in body.model_dump().items():
        database.set_cf_threshold(db, key, str(value))
    return cf_delegation.get_thresholds(db)


# Root endpoint for basic API health check
@app.get("/")
def read_root():
    logger.info("Root endpoint / hit")
    return {"message": "Welcome to DRep Tracker API"}


if __name__ == "__main__":
    # This block is for local development and testing with Uvicorn.
    # It won't be used when deploying with a proper ASGI server like Gunicorn + Uvicorn workers.
    import uvicorn

    logger.info(
        "Starting Uvicorn server for local development via if __name__ == '__main__'..."
    )
    print("Attempting to start Uvicorn from main.py's __main__ block...")
    # Uvicorn's `run` is blocking. It should be the last call if used this way.
    # Ensure the app object is referenced correctly, especially if using `reload=True`.
    # For `reload=True` to work effectively, Uvicorn often needs the app string like "backend.main:app".
    # However, if running `python backend/main.py`, "main:app" might be sought in the current dir.
    # Using `app=app` directly is safer when running the script directly.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=config.LOG_LEVEL.lower())
