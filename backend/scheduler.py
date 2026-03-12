import asyncio
import logging
import threading
import time

import httpx
import schedule
from sqlalchemy.exc import SQLAlchemyError

from . import config, data_manager, database

# Configure logger for this module
logger = logging.getLogger(__name__)


def job_update_drep_onchain_info():
    # Adding a print statement for immediate visibility in some environments
    print("SCHEDULER: Job 'job_update_drep_onchain_info' is attempting to run.")
    logger.info("SCHEDULER: Starting job_update_drep_onchain_info.")
    db_conn = None
    try:
        db_conn = database.get_db_connection()
        # Use asyncio.run to execute the async function from synchronous context
        asyncio.run(data_manager.update_drep_onchain_info_for_tracked(db_conn))
        logger.info("SCHEDULER: Finished job_update_drep_onchain_info.")
    except SQLAlchemyError as db_err:
        logger.error(
            f"SCHEDULER: Database error in job_update_drep_onchain_info: {db_err}",
            exc_info=True,
        )
    except httpx.RequestError as api_err:  # Catching specific requests error
        logger.error(
            f"SCHEDULER: API request error in job_update_drep_onchain_info: {api_err}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"SCHEDULER: Unexpected error in job_update_drep_onchain_info: {e}",
            exc_info=True,
        )
    finally:
        if db_conn:
            db_conn.close()
            logger.debug(
                "SCHEDULER: Database session closed for job_update_drep_onchain_info."
            )
    print("SCHEDULER: Job 'job_update_drep_onchain_info' finished.")


def job_update_drep_offchain_metadata():
    print("SCHEDULER: Job 'job_update_drep_offchain_metadata' is attempting to run.")
    logger.info("SCHEDULER: Starting job_update_drep_offchain_metadata.")
    db_conn = None
    try:
        db_conn = database.get_db_connection()
        asyncio.run(data_manager.update_drep_offchain_metadata_for_tracked(db_conn))
        logger.info("SCHEDULER: Finished job_update_drep_offchain_metadata.")
    except SQLAlchemyError as db_err:
        logger.error(
            f"SCHEDULER: Database error in job_update_drep_offchain_metadata: {db_err}",
            exc_info=True,
        )
    except httpx.RequestError as api_err:
        logger.error(
            f"SCHEDULER: API request error in job_update_drep_offchain_metadata: {api_err}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"SCHEDULER: Unexpected error in job_update_drep_offchain_metadata: {e}",
            exc_info=True,
        )
    finally:
        if db_conn:
            db_conn.close()
            logger.debug(
                "SCHEDULER: Database session closed for job_update_drep_offchain_metadata."
            )
    print("SCHEDULER: Job 'job_update_drep_offchain_metadata' finished.")


def job_update_cf_delegation_amounts():
    print("SCHEDULER: Job 'job_update_cf_delegation_amounts' is attempting to run.")
    logger.info("SCHEDULER: Starting job_update_cf_delegation_amounts.")
    db_conn = None
    try:
        db_conn = database.get_db_connection()
        asyncio.run(data_manager.update_cf_delegation_amounts(db_conn))
        logger.info("SCHEDULER: Finished job_update_cf_delegation_amounts.")
    except SQLAlchemyError as db_err:
        logger.error(
            f"SCHEDULER: Database error in job_update_cf_delegation_amounts: {db_err}",
            exc_info=True,
        )
    except httpx.RequestError as api_err:
        logger.error(
            f"SCHEDULER: API request error in job_update_cf_delegation_amounts: {api_err}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"SCHEDULER: Unexpected error in job_update_cf_delegation_amounts: {e}",
            exc_info=True,
        )
    finally:
        if db_conn:
            db_conn.close()
    print("SCHEDULER: Job 'job_update_cf_delegation_amounts' finished.")


def job_fetch_recent_gas_and_votes():
    print("SCHEDULER: Job 'job_fetch_recent_gas_and_votes' is attempting to run.")
    logger.info("SCHEDULER: Starting job_fetch_recent_gas_and_votes.")
    db_conn = None
    try:
        db_conn = database.get_db_connection()
        asyncio.run(data_manager.fetch_recent_governance_actions_and_votes(db_conn))
        logger.info("SCHEDULER: Finished job_fetch_recent_gas_and_votes.")
    except SQLAlchemyError as db_err:
        logger.error(
            f"SCHEDULER: Database error in job_fetch_recent_gas_and_votes: {db_err}",
            exc_info=True,
        )
    except httpx.RequestError as api_err:
        logger.error(
            f"SCHEDULER: API request error in job_fetch_recent_gas_and_votes: {api_err}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"SCHEDULER: Unexpected error in job_fetch_recent_gas_and_votes: {e}",
            exc_info=True,
        )
    finally:
        if db_conn:
            db_conn.close()
            logger.debug(
                "SCHEDULER: Database session closed for job_fetch_recent_gas_and_votes."
            )
    print("SCHEDULER: Job 'job_fetch_recent_gas_and_votes' finished.")


def run_scheduler():
    """Sets up the job schedule and runs the scheduler loop."""
    print("SCHEDULER: run_scheduler() called.")
    logger.info("SCHEDULER: Initializing scheduler and jobs...")

    # Schedule the jobs (using test intervals)
    schedule.every(1).minutes.do(job_update_drep_onchain_info)
    logger.info(
        "SCHEDULER: Scheduled 'job_update_drep_onchain_info' to run every 1 minute."
    )

    schedule.every(2).minutes.do(job_update_drep_offchain_metadata)
    logger.info(
        "SCHEDULER: Scheduled 'job_update_drep_offchain_metadata' to run every 2 minutes."
    )

    schedule.every(1).minutes.do(job_fetch_recent_gas_and_votes)
    logger.info(
        "SCHEDULER: Scheduled 'job_fetch_recent_gas_and_votes' to run every 1 minute."
    )

    schedule.every(10).minutes.do(job_update_cf_delegation_amounts)
    logger.info(
        "SCHEDULER: Scheduled 'job_update_cf_delegation_amounts' to run every 10 minutes."
    )

    logger.info(
        "SCHEDULER: Scheduler configured. Performing initial run of jobs upon startup..."
    )
    print("SCHEDULER: Performing initial run of scheduled jobs upon startup...")
    try:
        job_update_drep_onchain_info()
        job_update_drep_offchain_metadata()
        job_fetch_recent_gas_and_votes()
        job_update_cf_delegation_amounts()
        logger.info("SCHEDULER: Initial run of scheduled jobs complete.")
        print("SCHEDULER: Initial run of scheduled jobs complete.")
    except Exception as e:
        logger.error(
            f"SCHEDULER: Error during initial run of scheduled jobs: {e}", exc_info=True
        )
        print(f"SCHEDULER: Error during initial run of scheduled jobs: {e}")

    logger.info("SCHEDULER: Starting scheduler loop...")
    print("SCHEDULER: Starting scheduler loop...")
    while True:
        schedule.run_pending()
        time.sleep(1)  # Check every second for pending jobs


def start_scheduler_thread():
    """Starts the scheduler in a new thread."""
    print("SCHEDULER: start_scheduler_thread() called.")
    logger.info(
        "SCHEDULER: Ensuring database tables are created before starting scheduler thread."
    )
    try:
        database.create_tables_if_not_exist()
        logger.info(
            "SCHEDULER: Database tables verified/created successfully for scheduler startup."
        )
        print(
            "SCHEDULER: Database tables verified/created successfully for scheduler startup."
        )
    except Exception as e:
        logger.error(
            f"SCHEDULER: Critical error during database setup on scheduler startup: {e}",
            exc_info=True,
        )
        print(
            f"SCHEDULER: Critical error during database setup on scheduler startup: {e}"
        )
        logger.error("SCHEDULER: Scheduler will NOT start due to DB setup failure.")
        print("SCHEDULER: Scheduler will NOT start due to DB setup failure.")
        return

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.name = "SchedulerThread"
    scheduler_thread.start()
    logger.info("SCHEDULER: Scheduler thread started.")
    print("SCHEDULER: Scheduler thread started.")


if __name__ == "__main__":
    # This allows testing the scheduler setup independently.
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=config.LOG_LEVEL,
            format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )

    logger.info(
        "SCHEDULER: Running scheduler.py directly for testing (will run indefinitely)..."
    )
    print(
        "SCHEDULER: Running scheduler.py directly for testing (will run indefinitely)..."
    )

    database.create_tables_if_not_exist()

    # run_scheduler() # Uncomment to run the full scheduler loop for testing
    # For a quick test of job functions without waiting for schedule:
    logger.info(
        "SCHEDULER: Executing jobs directly for testing purposes (if __name__ == '__main__')..."
    )
    print(
        "SCHEDULER: Executing jobs directly for testing purposes (if __name__ == '__main__')..."
    )
    job_update_drep_onchain_info()
    job_update_drep_offchain_metadata()
    job_fetch_recent_gas_and_votes()
    logger.info("SCHEDULER: Test jobs executed directly. Exiting direct test run.")
    print("SCHEDULER: Test jobs executed directly. Exiting direct test run.")
    pass  # End of script for direct run test case
