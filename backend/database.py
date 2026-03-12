import logging
import os
import sqlite3 as stdlib_sqlite3

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from . import config, models

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)

# Setup SQLAlchemy
# Ensure the directory for the DB exists
db_dir = os.path.dirname(config.DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir)
    logger.info(f"Created directory for database: {db_dir}")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{config.DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    # echo=True # Uncomment to see generated SQL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_connection():
    """
    Returns a new SQLAlchemy Session.
    Renamed/aliased for compatibility, but callers must treat it as a Session.
    """
    return SessionLocal()


def create_tables_if_not_exist():
    """Creates database tables using SQLAlchemy models."""
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created using SQLAlchemy.")
    run_schema_migrations()


def run_schema_migrations():
    """Adds new columns to existing tables if they don't exist yet."""
    migrations = [
        ("dreps", "expires_epoch_no", "INTEGER"),
        ("dreps", "cf_delegated_ada", "BIGINT"),
        ("dreps", "delegation_epoch", "INTEGER"),
        ("dreps", "alignment_score", "INTEGER"),
        ("dreps", "delegation_date", "TEXT"),
        ("drep_votes", "has_rationale", "INTEGER DEFAULT 0"),
        ("drep_votes", "vote_anchor_url", "TEXT"),
        ("dreps", "cached_participation_rate", "REAL"),
        ("dreps", "cached_rationale_rate", "REAL"),
        ("dreps", "cached_cf_impact_ratio", "REAL"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                logger.info(f"Migration: added column {column} to {table}.")
            except Exception:
                conn.rollback()
                # Column likely already exists


# --- DRep Table Operations ---
def add_or_update_drep(db: Session, drep_data: dict):
    """Inserts or updates a DRep in the dreps table."""
    try:
        drep_id = drep_data.get("drep_id")
        if not drep_id:
            logger.error("Cannot add/update DRep without drep_id.")
            return

        existing_drep = db.scalar(
            select(models.DRep).where(models.DRep.drep_id == drep_id)
        )

        if existing_drep:
            # Update existing fields if provided in drep_data
            for key, value in drep_data.items():
                if hasattr(existing_drep, key):
                    setattr(existing_drep, key, value)
        else:
            # Create new DRep
            new_drep = models.DRep(**drep_data)
            db.add(new_drep)

        db.commit()
        logger.debug(f"DRep {drep_id} added or updated.")
    except Exception as e:
        logger.error(
            f"Error adding/updating DRep {drep_data.get('drep_id', 'UNKNOWN')}: {e}"
        )
        db.rollback()


def get_drep_by_id(db: Session, drep_id: str) -> dict | None:
    """Retrieves a DRep by their ID."""
    drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
    if drep:
        return {c.name: getattr(drep, c.name) for c in models.DRep.__table__.columns}
    return None


def update_drep_metadata_status(
    db: Session, drep_id: str, status: str, check_date: str
):
    try:
        drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
        if drep:
            drep.metadata_status = status
            drep.last_metadata_check_date = check_date
            db.commit()
            logger.debug(f"Updated metadata status for DRep {drep_id} to {status}.")
        else:
            logger.warning(f"Could not find DRep {drep_id} to update metadata status.")
    except Exception as e:
        logger.error(f"Error updating metadata status for DRep {drep_id}: {e}")
        db.rollback()


def update_drep_activity_status(
    db: Session, drep_id: str, status: str, last_epoch: int | None
):
    try:
        drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
        if drep:
            drep.activity_status = status
            drep.last_koios_update_epoch = last_epoch
            db.commit()
            logger.debug(f"Updated activity status for DRep {drep_id} to {status}.")
        else:
            logger.warning(f"Could not find DRep {drep_id} to update activity status.")
    except Exception as e:
        logger.error(f"Error updating activity status for DRep {drep_id}: {e}")
        db.rollback()


# --- Governance Actions Table Operations ---
def add_governance_action(db: Session, ga_data: dict):
    """Inserts a governance action if it doesn't exist."""
    try:
        ga_id = ga_data.get("ga_id")
        existing_ga = db.scalar(
            select(models.GovernanceAction).where(
                models.GovernanceAction.ga_id == ga_id
            )
        )
        if not existing_ga:
            new_ga = models.GovernanceAction(**ga_data)
            db.add(new_ga)
            db.commit()
            logger.debug(f"Governance action {ga_id} added.")
        else:
            logger.debug(f"Governance action {ga_id} already exists.")
    except Exception as e:
        logger.error(
            f"Error adding governance action {ga_data.get('ga_id', 'UNKNOWN')}: {e}"
        )
        db.rollback()


def get_ga_by_id(db: Session, ga_id: str) -> dict | None:
    """Retrieves a governance action by its ID."""
    ga = db.scalar(
        select(models.GovernanceAction).where(models.GovernanceAction.ga_id == ga_id)
    )
    if ga:
        return {
            c.name: getattr(ga, c.name)
            for c in models.GovernanceAction.__table__.columns
        }
    return None


def get_all_ga_ids(db: Session) -> list[str]:
    """Retrieves all governance action IDs."""
    result = db.execute(select(models.GovernanceAction.ga_id))
    return [row[0] for row in result.all()]


# --- DRep Votes Table Operations ---
def add_drep_vote(db: Session, vote_data: dict):
    """Inserts or updates a DRep vote, keeping rationale/anchor data current."""
    try:
        drep_id = vote_data.get("drep_id")
        ga_id = vote_data.get("ga_id")
        existing_vote = db.scalar(
            select(models.Vote).where(
                models.Vote.drep_id == drep_id, models.Vote.ga_id == ga_id
            )
        )
        if not existing_vote:
            new_vote = models.Vote(**vote_data)
            db.add(new_vote)
            db.commit()
            logger.debug(f"Vote by DRep {drep_id} on GA {ga_id} added.")
        else:
            # Update fields that may have changed (vote change or rationale added later)
            changed = False
            for field in ("vote", "voted_epoch", "has_rationale", "vote_anchor_url"):
                new_val = vote_data.get(field)
                if new_val is not None and getattr(existing_vote, field) != new_val:
                    setattr(existing_vote, field, new_val)
                    changed = True
            if changed:
                db.commit()
                logger.debug(f"Vote by DRep {drep_id} on GA {ga_id} updated.")
    except Exception as e:
        logger.error(
            f"Error adding DRep vote for DRep {vote_data.get('drep_id')} on GA {vote_data.get('ga_id')}: {e}"
        )
        db.rollback()


# --- Tracked DReps Table Operations ---
def add_tracked_drep(db: Session, drep_id: str):
    """Adds a DRep to the tracked_dreps table."""
    try:
        # Ensure DRep exists in main table first (ORM handles FK, but good to ensure presence)
        if not get_drep_by_id(db, drep_id):
            logger.info(
                f"DRep {drep_id} not in 'dreps' table. Adding minimal entry before tracking."
            )
            add_or_update_drep(db, {"drep_id": drep_id})

        existing_tracked = db.scalar(
            select(models.TrackedDRep).where(models.TrackedDRep.drep_id == drep_id)
        )
        if not existing_tracked:
            new_tracked = models.TrackedDRep(drep_id=drep_id)
            db.add(new_tracked)
            db.commit()
            logger.info(f"DRep {drep_id} added to tracked_dreps.")
        else:
            logger.debug(f"DRep {drep_id} is already in tracked_dreps.")
    except Exception as e:
        logger.error(f"Error adding DRep {drep_id} to tracked_dreps: {e}")
        db.rollback()


def remove_tracked_drep(db: Session, drep_id: str):
    try:
        tracked = db.scalar(
            select(models.TrackedDRep).where(models.TrackedDRep.drep_id == drep_id)
        )
        if tracked:
            db.delete(tracked)
            db.commit()
            logger.info(f"DRep {drep_id} removed from tracked_dreps.")
    except Exception as e:
        logger.error(f"Error removing DRep {drep_id} from tracked_dreps: {e}")
        db.rollback()


def get_tracked_drep_ids(db: Session) -> list[str]:
    result = db.execute(select(models.TrackedDRep.drep_id))
    return [row[0] for row in result.all()]


def get_all_tracked_drep_details(db: Session) -> list[dict]:
    """Retrieves full details for all DReps listed in the tracked_dreps table."""
    # Using join
    query = (
        select(models.DRep)
        .join(models.TrackedDRep, models.DRep.drep_id == models.TrackedDRep.drep_id)
        .order_by(models.DRep.drep_id)
    )
    dreps = db.scalars(query).all()
    return [
        {c.name: getattr(d, c.name) for c in models.DRep.__table__.columns}
        for d in dreps
    ]


def get_all_governance_actions(
    db: Session, limit: int = 100, offset: int = 0
) -> list[dict]:
    """Retrieves governance actions with pagination."""
    query = (
        select(models.GovernanceAction)
        .order_by(
            models.GovernanceAction.submission_epoch.desc(),
            models.GovernanceAction.ga_id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    gas = db.scalars(query).all()
    return [
        {c.name: getattr(ga, c.name) for c in models.GovernanceAction.__table__.columns}
        for ga in gas
    ]


def get_votes_for_ga(
    db: Session, ga_id: str, limit: int = 100, offset: int = 0
) -> list[dict]:
    """Retrieves votes for a specific governance action ID."""
    query = (
        select(models.Vote)
        .where(models.Vote.ga_id == ga_id)
        .order_by(models.Vote.drep_id)
        .limit(limit)
        .offset(offset)
    )
    votes = db.scalars(query).all()
    # Need to verify if 'vote_id' is needed, but returning all columns including vote_id if present
    columns = models.Vote.__table__.columns
    return [{c.name: getattr(v, c.name) for c in columns} for v in votes]


# --- Voting Power Snapshots Table Operations ---
def add_or_update_voting_power_snapshot(
    db: Session, drep_id: str, epoch: int, voting_power: int, delegator_count: int
):
    """Inserts or updates a voting power snapshot for a DRep at a given epoch."""
    try:
        existing = db.scalar(
            select(models.VotingPowerSnapshot).where(
                models.VotingPowerSnapshot.drep_id == drep_id,
                models.VotingPowerSnapshot.epoch == epoch,
            )
        )
        if existing:
            existing.voting_power = voting_power
            existing.delegator_count = delegator_count
        else:
            snapshot = models.VotingPowerSnapshot(
                drep_id=drep_id,
                epoch=epoch,
                voting_power=voting_power,
                delegator_count=delegator_count,
            )
            db.add(snapshot)
        db.commit()
        logger.debug(
            f"Voting power snapshot for DRep {drep_id} at epoch {epoch} added/updated."
        )
    except Exception as e:
        logger.error(
            f"Error adding/updating voting power snapshot for DRep {drep_id} at epoch {epoch}: {e}"
        )
        db.rollback()


def get_voting_power_history(
    db: Session, drep_id: str, limit: int = 50, offset: int = 0
) -> list[dict]:
    """Retrieves voting power snapshots for a DRep, ordered by epoch descending."""
    query = (
        select(models.VotingPowerSnapshot)
        .where(models.VotingPowerSnapshot.drep_id == drep_id)
        .order_by(models.VotingPowerSnapshot.epoch.desc())
        .limit(limit)
        .offset(offset)
    )
    snapshots = db.scalars(query).all()
    return [
        {
            "drep_id": s.drep_id,
            "epoch": s.epoch,
            "voting_power": s.voting_power,
            "delegator_count": s.delegator_count,
        }
        for s in snapshots
    ]


def get_votes_by_drep(
    db: Session, drep_id: str, limit: int = 100, offset: int = 0
) -> list[dict]:
    """Retrieves votes cast by a specific DRep ID."""
    query = (
        select(models.Vote)
        .where(models.Vote.drep_id == drep_id)
        .order_by(models.Vote.ga_id)
        .limit(limit)
        .offset(offset)
    )
    votes = db.scalars(query).all()
    columns = models.Vote.__table__.columns
    return [{c.name: getattr(v, c.name) for c in columns} for v in votes]


def get_vote_count_for_ga(db: Session, ga_id: str) -> int:
    """Returns the number of votes stored for a given governance action."""
    count = db.scalar(
        select(func.count()).select_from(models.Vote).where(models.Vote.ga_id == ga_id)
    )
    return count if count else 0


# --- Vote Matrix Operations ---
def get_votes_for_ga_by_dreps(
    db: Session, ga_id: str, drep_ids: list[str]
) -> list[dict]:
    """Retrieves votes for a GA filtered to specific DRep IDs."""
    if not drep_ids:
        return []
    query = (
        select(models.Vote)
        .where(models.Vote.ga_id == ga_id, models.Vote.drep_id.in_(drep_ids))
    )
    votes = db.scalars(query).all()
    columns = models.Vote.__table__.columns
    return [{c.name: getattr(v, c.name) for c in columns} for v in votes]


# --- CF Delegation Operations ---
def get_cf_delegated_dreps(db: Session) -> list[dict]:
    """Retrieves all tracked DReps (same source of truth as DRepManagement)."""
    query = (
        select(models.DRep)
        .join(models.TrackedDRep, models.DRep.drep_id == models.TrackedDRep.drep_id)
        .order_by(models.DRep.drep_id)
    )
    dreps = db.scalars(query).all()
    return [
        {c.name: getattr(d, c.name) for c in models.DRep.__table__.columns}
        for d in dreps
    ]


def count_gas_since_epoch(db: Session, epoch: int) -> int:
    """Counts governance actions submitted since a given epoch."""
    count = db.scalar(
        select(func.count())
        .select_from(models.GovernanceAction)
        .where(models.GovernanceAction.submission_epoch >= epoch)
    )
    return count if count else 0


def count_drep_votes_since_epoch(db: Session, drep_id: str, epoch: int) -> int:
    """Counts votes cast by a DRep on governance actions submitted since a given epoch."""
    count = db.scalar(
        select(func.count())
        .select_from(models.Vote)
        .join(models.GovernanceAction, models.Vote.ga_id == models.GovernanceAction.ga_id)
        .where(
            models.Vote.drep_id == drep_id,
            models.GovernanceAction.submission_epoch >= epoch,
        )
    )
    return count if count else 0


def count_drep_votes_with_rationale(db: Session, drep_id: str, epoch: int) -> int:
    """Counts votes with rationale by a DRep on governance actions submitted since a given epoch."""
    count = db.scalar(
        select(func.count())
        .select_from(models.Vote)
        .join(models.GovernanceAction, models.Vote.ga_id == models.GovernanceAction.ga_id)
        .where(
            models.Vote.drep_id == drep_id,
            models.GovernanceAction.submission_epoch >= epoch,
            models.Vote.has_rationale == 1,
        )
    )
    return count if count else 0


def update_drep_cached_metrics(db: Session, drep_id: str, metrics: dict):
    """Updates cached computed metrics for a DRep."""
    try:
        drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
        if drep:
            for key in ("cached_participation_rate", "cached_rationale_rate", "cached_cf_impact_ratio"):
                if key in metrics:
                    setattr(drep, key, metrics[key])
            db.commit()
    except Exception as e:
        logger.error(f"Error updating cached metrics for DRep {drep_id}: {e}")
        db.rollback()


def get_earliest_vote_epoch(db: Session, drep_id: str) -> int | None:
    """Returns the earliest voted_epoch for a DRep from the drep_votes table."""
    result = db.scalar(
        select(func.min(models.Vote.voted_epoch)).where(
            models.Vote.drep_id == drep_id
        )
    )
    return result


def update_drep_alignment_score(db: Session, drep_id: str, score: int):
    """Updates the alignment score for a DRep."""
    try:
        drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
        if drep:
            drep.alignment_score = score
            db.commit()
    except Exception as e:
        logger.error(f"Error updating alignment score for DRep {drep_id}: {e}")
        db.rollback()


def update_drep_cf_delegation(
    db: Session, drep_id: str, cf_delegated_ada: int | None, delegation_epoch: int
):
    """Updates CF delegation data for a DRep."""
    try:
        drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
        if drep:
            drep.cf_delegated_ada = cf_delegated_ada
            drep.delegation_epoch = delegation_epoch
            db.commit()
    except Exception as e:
        logger.error(f"Error updating CF delegation for DRep {drep_id}: {e}")
        db.rollback()


def update_drep_delegation_date(db: Session, drep_id: str, delegation_date: str | None):
    """Updates the user-set delegation date for a DRep."""
    try:
        drep = db.scalar(select(models.DRep).where(models.DRep.drep_id == drep_id))
        if drep:
            drep.delegation_date = delegation_date
            db.commit()
    except Exception as e:
        logger.error(f"Error updating delegation_date for DRep {drep_id}: {e}")
        db.rollback()


def get_cf_thresholds(db: Session) -> dict:
    """Retrieves CF delegation thresholds from DB."""
    result = {}
    rows = db.scalars(select(models.CFDelegationThreshold)).all()
    for row in rows:
        result[row.key] = row.value
    return result


def set_cf_threshold(db: Session, key: str, value: str):
    """Sets a CF delegation threshold value."""
    try:
        existing = db.scalar(
            select(models.CFDelegationThreshold).where(
                models.CFDelegationThreshold.key == key
            )
        )
        if existing:
            existing.value = value
        else:
            new_threshold = models.CFDelegationThreshold(key=key, value=value)
            db.add(new_threshold)
        db.commit()
    except Exception as e:
        logger.error(f"Error setting CF threshold {key}: {e}")
        db.rollback()


if __name__ == "__main__":
    logger.info("--- Testing Database Functions (ORM) ---")
    create_tables_if_not_exist()
    db_conn = get_db_connection()  # Now returns a Session

    try:
        logger.info("\nTesting add_or_update_drep...")
        test_drep_id = "drep_test_main_db_script"
        if config.INITIAL_DREP_LIST and test_drep_id in config.INITIAL_DREP_LIST:
            test_drep_id = "drep_test_unique_main_db"

        drep_details = {
            "drep_id": test_drep_id,
            "name": "Test DRep Main",
            "registration_epoch": 100,
            "total_voting_power": 1000000,
            "delegator_count": 50,
            "activity_status": "Active",
            "last_koios_update_epoch": 105,
        }
        add_or_update_drep(db_conn, drep_details)
        retrieved_drep = get_drep_by_id(db_conn, test_drep_id)
        logger.info(f"Retrieved DRep {test_drep_id}: {retrieved_drep}")
        assert retrieved_drep is not None and retrieved_drep["name"] == "Test DRep Main"

        updated_drep_details = {
            "drep_id": test_drep_id,
            "name": "Test DRep Updated",
            "total_voting_power": 1200000,
        }
        add_or_update_drep(db_conn, updated_drep_details)
        retrieved_drep_updated = get_drep_by_id(db_conn, test_drep_id)
        logger.info(f"Retrieved updated DRep {test_drep_id}: {retrieved_drep_updated}")
        assert retrieved_drep_updated["name"] == "Test DRep Updated"
        assert retrieved_drep_updated["total_voting_power"] == 1200000

        logger.info("\nTesting add_tracked_drep...")
        add_tracked_drep(db_conn, test_drep_id)
        tracked_ids = get_tracked_drep_ids(db_conn)
        logger.info(f"Tracked DRep IDs: {tracked_ids}")
        assert test_drep_id in tracked_ids

        logger.info("\nTesting get_all_tracked_drep_details...")
        tracked_details = get_all_tracked_drep_details(db_conn)
        logger.info(f"Found {len(tracked_details)} tracked DRep details.")
        assert len(tracked_details) > 0

        logger.info("\nTesting add_governance_action...")
        test_ga_id = "ga_test_main_db_script"
        ga_details = {
            "ga_id": test_ga_id,
            "title": "Test GA Main",
            "type": "InfoAction",
            "submission_epoch": 102,
            "tx_hash": "txhash_dummy_ga_main",
            "cert_index": 0,
        }
        add_governance_action(db_conn, ga_details)
        retrieved_ga = get_ga_by_id(db_conn, test_ga_id)
        logger.info(f"Retrieved GA {test_ga_id}: {retrieved_ga}")
        assert retrieved_ga is not None and retrieved_ga["title"] == "Test GA Main"

        logger.info("\nTesting add_drep_vote...")
        vote_details = {
            "drep_id": test_drep_id,
            "ga_id": test_ga_id,
            "vote": "Yes",
            "voted_epoch": 103,
        }
        add_drep_vote(db_conn, vote_details)

        # Checking vote via count to avoid raw sql in test
        vote_count = get_vote_count_for_ga(db_conn, test_ga_id)
        logger.info(f"Retrieved vote count for GA: {vote_count}")
        assert vote_count >= 1

        logger.info("\n--- Database Function Tests Complete ---")

    except AssertionError as ae:
        logger.error(f"Assertion failed during testing: {ae}")
        raise
    except Exception as e:
        logger.error(
            f"An error occurred during database function testing: {e}", exc_info=True
        )
        raise
    finally:
        db_conn.close()
        logger.info("Database connection closed.")
