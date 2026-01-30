from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class DRep(Base):
    __tablename__ = "dreps"

    drep_id = Column(String, primary_key=True)
    name = Column(String)
    registration_epoch = Column(Integer)
    registration_date = Column(String)
    metadata_url = Column(String)
    metadata_hash = Column(String)
    metadata_status = Column(String, default="Not Fetched Yet")
    total_voting_power = Column(BigInteger, default=0)
    delegator_count = Column(Integer, default=0)
    activity_status = Column(String, default="Unknown")
    last_koios_update_epoch = Column(Integer)
    last_metadata_check_date = Column(String)

    # Relationships
    votes = relationship("Vote", back_populates="drep")
    tracked_entry = relationship("TrackedDRep", back_populates="drep", uselist=False)
    voting_power_snapshots = relationship("VotingPowerSnapshot", back_populates="drep")


class TrackedDRep(Base):
    __tablename__ = "tracked_dreps"

    drep_id = Column(String, ForeignKey("dreps.drep_id"), primary_key=True)

    # Relationships
    drep = relationship("DRep", back_populates="tracked_entry")


class GovernanceAction(Base):
    __tablename__ = "governance_actions"

    ga_id = Column(String, primary_key=True)  # tx_hash#cert_index
    title = Column(String)
    type = Column(String)
    submission_epoch = Column(Integer)
    submission_date = Column(String)
    expiration_epoch = Column(Integer)
    expiration_date = Column(String)
    tx_hash = Column(String)
    cert_index = Column(Integer)

    # Relationships
    votes = relationship("Vote", back_populates="governance_action")


class Vote(Base):
    __tablename__ = "drep_votes"

    # We use a composite primary key or a surrogate key.
    # Since the original table had a UNIQUE(drep_id, ga_id), we can model that.
    # We'll use a surrogate integer ID for easier ORM handling, but since unique logic is key,
    # let's assume we might need to add an integer PK if one didn't exist, OR use composite PK.
    # Examining database_setup.py (which I can't see but `database.py` insert implies):
    # It probably didn't have an 'id' column, just the composite unique constraint which usually implies composite PK or just a unique index.
    # For simpler migration on existing schema without migration tool, let's map the existing columns.
    # If the table structure strictly has no 'id', mapping it without one in SQLAlchemy requires defining a composite PK.

    vote_id = Column(
        Integer, primary_key=True, autoincrement=True
    )  # Adding this assumes new schema or existing rowid mapping.
    # WAIT. If I add a column here that doesn't exist in the DB, it will fail.
    # Existing SQLite tables have an implicit rowid.
    # To be safe with EXISTING schema, I should likely use composite primary key on (drep_id, ga_id).

    drep_id = Column(String, ForeignKey("dreps.drep_id"), nullable=False)
    ga_id = Column(String, ForeignKey("governance_actions.ga_id"), nullable=False)
    vote = Column(String)
    voted_epoch = Column(Integer)

    __table_args__ = (UniqueConstraint("drep_id", "ga_id", name="_drep_ga_uc"),)

    # Relationships
    drep = relationship("DRep", back_populates="votes")
    governance_action = relationship("GovernanceAction", back_populates="votes")


class VotingPowerSnapshot(Base):
    __tablename__ = "voting_power_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    drep_id = Column(String, ForeignKey("dreps.drep_id"), nullable=False)
    epoch = Column(Integer, nullable=False)
    voting_power = Column(BigInteger, nullable=False)
    delegator_count = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("drep_id", "epoch", name="_drep_epoch_uc"),
    )

    # Relationships
    drep = relationship("DRep", back_populates="voting_power_snapshots")
