from typing import Dict, List, Optional

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
    expires_epoch_no: Optional[int] = None
    last_koios_update_epoch: Optional[int] = None
    last_metadata_check_date: Optional[str] = None  # ISO 8601 date string
    # CF Delegation fields
    cf_delegated_ada: Optional[int] = None
    delegation_epoch: Optional[int] = None
    delegation_date: Optional[str] = None  # User-set ISO date string (YYYY-MM-DD)
    alignment_score: Optional[int] = None


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
    has_rationale: Optional[int] = Field(default=0)
    vote_anchor_url: Optional[str] = None


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


# --- Combined Response Models ---
class DRepWithVotes(DRep):
    votes: List[DRepVote] = []


class GovernanceActionWithVotes(GovernanceAction):
    votes_summary: Optional[dict] = None
    drep_votes: List[DRepVote] = []


class GovernanceActionVoter(BaseModel):
    drep_id: str
    vote: str

    class Config:
        from_attributes = True


# --- Vote Matrix Schemas ---
class VoteMatrixGA(GovernanceAction):
    drep_votes: Dict[str, str] = {}  # drep_id -> vote value


class VoteMatrixResponse(BaseModel):
    governance_actions: List[VoteMatrixGA] = []
    total_count: int = 0


# --- CF Delegation Schemas ---
class CFDelegationDRepResponse(DRep):
    tenure_days: Optional[int] = None
    cf_impact_ratio: Optional[float] = None
    participation_rate: Optional[float] = None
    rationale_rate: Optional[float] = None
    is_at_risk: bool = False
    failed_gate: Optional[str] = None
    votes_cast: Optional[int] = None
    total_gas: Optional[int] = None


class DelegationDateUpdate(BaseModel):
    delegation_date: Optional[str] = None  # ISO date string YYYY-MM-DD, or null to clear


class CFThresholdSettings(BaseModel):
    mature_cohort_days: int = 180
    exception_tenure_days: int = 60
    exception_participation_pct: float = 40.0
    part_lower_bound_pct: float = 50.0
    part_upper_bound_pct: float = 67.0
    impact_minimum_pct: float = 30.0


class AlignmentScoreUpdate(BaseModel):
    score: int = Field(..., ge=1, le=5)


class CFDelegationUpdate(BaseModel):
    delegation_epoch: int
    cf_delegated_ada: Optional[int] = None
