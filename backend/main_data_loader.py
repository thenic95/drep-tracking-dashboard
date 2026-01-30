import logging

from . import (
    config,  # To access LOG_LEVEL for example
    data_manager,
    database,
)

# Configure logging
# Ensure console output for this script
logger = logging.getLogger()  # Get the root logger
logger.setLevel(config.LOG_LEVEL)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s"
)

# Clear existing handlers if any (e.g., from basicConfig in other modules)
# for handler in logger.handlers[:]:
#     logger.removeHandler(handler)

# Add a stream handler to output to console
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
if not any(
    isinstance(h, logging.StreamHandler) for h in logger.handlers
):  # Avoid duplicate stream handlers
    logger.addHandler(stream_handler)


def run_initial_load():
    """
    Performs the initial data load for the DRep Tracker.
    - Ensures database and tables are created.
    - Syncs the initial list of DReps to be tracked.
    - Fetches and updates information for these tracked DReps.
    - Fetches all governance actions and their associated DRep votes.
    """
    logger.info("Starting initial data load process...")

    # 1. Ensure database and tables exist
    logger.info("Step 1: Ensuring database and tables are created...")
    try:
        database.create_tables_if_not_exist()
        logger.info("Database and tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Critical error during database setup: {e}")
        logger.error("Initial data load cannot proceed without database. Exiting.")
        return

    # 2. Get a database connection
    db_conn = None
    try:
        db_conn = database.get_db_connection()
        if db_conn is None:
            logger.error(
                "Failed to establish database connection. Aborting initial load."
            )
            return
        logger.info("Database connection established.")

        # 3. Sync initial DReps from config to the tracked_dreps table
        logger.info("\nStep 2: Syncing initial DRep list to tracked_dreps table...")
        data_manager.sync_initial_dreps_to_tracked_list(db_conn)
        logger.info("Initial DRep list synced.")

        # 4. Update/fetch full information for these tracked DReps
        logger.info("\nStep 3: Updating/fetching full information for tracked DReps...")
        data_manager.update_tracked_dreps_full_info(db_conn)
        logger.info("Tracked DReps information updated.")

        # 5. Fetch all governance actions and their DRep votes
        logger.info(
            "\nStep 4: Processing all governance actions and their DRep votes..."
        )
        data_manager.fetch_recent_governance_actions_and_votes(db_conn)
        logger.info("Governance actions and DRep votes processed.")

        logger.info("\nInitial data load process completed successfully!")

    except sqlite3.Error as db_err:
        logger.error(f"A database error occurred during the initial load: {db_err}")
    except requests.exceptions.RequestException as api_err:
        logger.error(
            f"An API request error occurred during the initial load: {api_err}"
        )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during the initial load: {e}", exc_info=True
        )
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database connection closed.")


if __name__ == "__main__":
    import sqlite3  # For specific exception type

    import requests  # For specific exception type

    # Ensure logger is available if script is run directly
    # This setup is similar to the top of the file, might be redundant if Python execution model handles it.
    if not logging.getLogger().handlers:  # Check if root logger has handlers
        logging.basicConfig(
            level=config.LOG_LEVEL,
            format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )

    logger.info("main_data_loader.py executed as __main__")
    run_initial_load()
