from typing import List, Optional

from pydantic import BaseModel, Field


# --- DRep Schemas ---
class DRepBase(BaseModel):
    drep_id: str = Field(..., description="The DRep ID (CIP-129 Bech32 format or hex)")
    name: Optional[str] = None
    registration_epoch: Optional[int] = None
    registration_date: Optional[str] = None  # ISO 8601 date string
    metadata_url: Optional[str] = None
    metadata_hash: Optional[str] = None
    metadata_status: Optional[str] = Field(default="Not Fetched Yet")
    total_voting_power: Optional[int] = Field(default=0)
    delegator_count: Optional[int] = Field(default=0)
    activity_status: Optional[str] = Field(default="Unknown")
    last_koios_update_epoch: Optional[int] = None
    last_metadata_check_date: Optional[str] = None  # ISO 8601 date string


class DRepCreate(DRepBase):
    pass  # For creation, drep_id is key, others can be optional or defaulted


class DRep(DRepBase):
    class Config:
        from_attributes = True  #  Change from orm_mode for Pydantic v2


# --- Governance Action Schemas ---
class GovernanceActionBase(BaseModel):
    ga_id: str = Field(
        ...,
        description="Governance Action ID (e.g., txhash_certindex or CIP-129 Bech32)",
    )
    title: Optional[str] = None
    type: Optional[str] = None
    submission_epoch: Optional[int] = None
    submission_date: Optional[str] = None  # ISO 8601 date string
    expiration_epoch: Optional[int] = None
    expiration_date: Optional[str] = None  # ISO 8601 date string
    tx_hash: str
    cert_index: int


class GovernanceActionCreate(GovernanceActionBase):
    pass


class GovernanceAction(GovernanceActionBase):
    class Config:
        from_attributes = True


# --- DRep Vote Schemas ---
class DRepVoteBase(BaseModel):
    drep_id: str
    ga_id: str
    vote: str  # e.g., "Yes", "No", "Abstain"
    voted_epoch: Optional[int] = None
    # vote_id is auto-incrementing in DB, usually not needed in create, but present in response


class DRepVoteCreate(DRepVoteBase):
    pass


class DRepVote(DRepVoteBase):
    vote_id: int  # Include vote_id from the database in responses

    class Config:
        from_attributes = True


# --- TrackedDRep Schemas ---
class TrackedDRep(BaseModel):
    drep_id: str

    class Config:
        from_attributes = True


# --- Voting Power Snapshot Schemas ---
class VotingPowerSnapshot(BaseModel):
    drep_id: str
    epoch: int
    voting_power: int = Field(..., description="Voting power in lovelace")
    delegator_count: int

    class Config:
        from_attributes = True


# --- Combined Response Models (Examples) ---
class DRepWithVotes(DRep):
    votes: List[DRepVote] = []


class GovernanceActionWithVotes(GovernanceAction):
    votes_summary: Optional[dict] = None  # e.g., {"yes": 10, "no": 5, "abstain": 2}
    drep_votes: List[DRepVote] = []  # Detailed votes by DReps


# For API responses where we might just list DRep IDs for a GA
class GovernanceActionVoter(BaseModel):
    drep_id: str
    vote: str

    class Config:
        from_attributes = True
