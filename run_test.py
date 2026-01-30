import logging
import sqlite3
import os

# Adjust import paths if necessary, assuming run_test.py is in the root directory
# and backend is a subdirectory.
from backend import database, data_manager, config

# Configure basic logging for the test
log_file_path = 'test_run.log'
# Delete log file if it exists
if os.path.exists(log_file_path):
    os.remove(log_file_path)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path), # Log to a file
        logging.StreamHandler() # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# DRep IDs to check, ensure these are in config.INITIAL_DREP_LIST
DREP_IDS_TO_TEST = [
    "drep1y2eu92qwy875nlslg3ahlh0hy5vhzpkrjay88ptvdp0z6cqm9h25x",
    "drep1yglrf4el8gghum239fggvfrau25k2576y4dvcz65r2ukj8sqpsc2k",
    "drep1yfjez5zup0gystdvc933w2mn8k64hcy3krvc2namluwjxdcfhm8wd",
    "drep1ytcv4ax77s0enqef56qjflf4d8zjgxulukme9uf5p8cfaagysjppn",
    "drep1ytzshxuma6cwrnlv2ucyclfqw3k4nu4nuudmh2z87j9hncsk9dhy4",
    "drep1yfa8r8r36x7x05htftce7qhafrn5nzzr6vazy95pzy6y5dqac0ss7",
    "drep1yv4uesaj92wk8ljlsh4p7jzndnzrflchaz5fzug3zxg4naqkpeas3",
]

def main():
    logger.info("Starting DRep registration epoch test.")

    # Ensure the database directory exists (if DB_PATH includes a directory)
    db_directory = os.path.dirname(config.DB_PATH)
    if db_directory and not os.path.exists(db_directory):
        os.makedirs(db_directory)
        logger.info(f"Created database directory: {db_directory}")

    # 0. Delete existing database file for a fresh start
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
        logger.info(f"Deleted existing database file: {config.DB_PATH}")


    # 1. Initialize database and get connection
    logger.info("Initializing database...")
    database.create_tables_if_not_exist() # Uses config.DB_PATH
    conn = None
    try:
        conn = database.get_db_connection() # Uses config.DB_PATH
        logger.info("Database connection established.")

        # 2. Sync initial DReps (this will add them to tracked_dreps and dreps tables)
        logger.info("Syncing initial DReps to tracked list...")
        data_manager.sync_initial_dreps_to_tracked_list(conn)
        logger.info("Initial DReps synced.")

        # Verify they are in the dreps table, possibly with null registration info
        logger.info("DReps in 'dreps' table before on-chain info update (first few):")
        cursor = conn.cursor()
        cursor.execute("SELECT drep_id, registration_epoch, registration_date FROM dreps LIMIT 5")
        for row in cursor.fetchall():
            logger.info(f"  Pre-check: {row}")

        # 3. Run data update process
        logger.info("Running update_drep_onchain_info_for_tracked...")
        data_manager.update_drep_onchain_info_for_tracked(conn)
        logger.info("update_drep_onchain_info_for_tracked completed.")

        # 4. Verify results
        logger.info("\n--- Verification Results ---")
        for drep_id in DREP_IDS_TO_TEST:
            cursor.execute("SELECT drep_id, registration_epoch, registration_date, activity_status, metadata_url FROM dreps WHERE drep_id = ?", (drep_id,))
            row = cursor.fetchone()
            if row:
                logger.info(f"DRep ID: {row[0]}")
                logger.info(f"  Registration Epoch: {row[1]}")
                logger.info(f"  Registration Date: {row[2]}")
                logger.info(f"  Activity Status: {row[3]}")
                logger.info(f"  Metadata URL: {row[4]}")
            else:
                logger.warning(f"DRep ID: {drep_id} - NOT FOUND IN DATABASE.")
        logger.info("--- End of Verification Results ---")

    except sqlite3.Error as e:
        logger.error(f"A database error occurred: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")
    
    logger.info(f"Test run finished. Check '{log_file_path}' for detailed logs.")

if __name__ == "__main__":
    main()
