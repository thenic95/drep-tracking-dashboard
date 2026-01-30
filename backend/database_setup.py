import sqlite3

DB_NAME = "drep_tracker.db"


def create_tables(db_name=DB_NAME):
    """
    Connects to a SQLite database and creates the required tables if they don't already exist.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # --- dreps table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dreps (
            drep_id TEXT PRIMARY KEY,
            name TEXT,
            registration_epoch INTEGER,
            registration_date TEXT,
            metadata_url TEXT,
            metadata_hash TEXT,
            metadata_status TEXT DEFAULT 'Not Fetched Yet',
            total_voting_power BIGINT DEFAULT 0,
            delegator_count INTEGER DEFAULT 0,
            activity_status TEXT DEFAULT 'Unknown',
            last_koios_update_epoch INTEGER,
            last_metadata_check_date TEXT
        )
        """)
        print("Table 'dreps' created or already exists.")

        # --- governance_actions table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS governance_actions (
            ga_id TEXT PRIMARY KEY,
            title TEXT,
            type TEXT,
            submission_epoch INTEGER,
            submission_date TEXT,
            expiration_epoch INTEGER,
            expiration_date TEXT,
            tx_hash TEXT NOT NULL,
            cert_index INTEGER NOT NULL
        )
        """)
        print("Table 'governance_actions' created or already exists.")

        # --- drep_votes table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drep_votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
            drep_id TEXT NOT NULL,
            ga_id TEXT NOT NULL,
            vote TEXT NOT NULL,
            voted_epoch INTEGER,
            FOREIGN KEY (drep_id) REFERENCES dreps (drep_id),
            FOREIGN KEY (ga_id) REFERENCES governance_actions (ga_id),
            UNIQUE (drep_id, ga_id)
        )
        """)
        print("Table 'drep_votes' created or already exists.")

        # --- tracked_dreps table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracked_dreps (
            drep_id TEXT PRIMARY KEY,
            FOREIGN KEY (drep_id) REFERENCES dreps (drep_id)
        )
        """)
        print("Table 'tracked_dreps' created or already exists.")

        conn.commit()
        print(f"Database '{db_name}' initialized successfully with all tables.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_tables()
    # Basic check to see if the db file is created
    # In a real environment, you might connect and query PRAGMA table_info('table_name')
    import os

    if os.path.exists(DB_NAME):
        print(f"Database file '{DB_NAME}' found.")
    else:
        print(f"Database file '{DB_NAME}' NOT found.")
