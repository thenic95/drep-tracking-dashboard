# PRD: DRep Profile Pages

## 1. Overview

Add individual profile pages for each tracked DRep, accessible at `/dreps/:drepId`. Each profile page displays key statistics (total votes, total delegators, total voting power), a voting power over time chart, and a complete vote history table.

## 2. Problem Statement

The current dashboard provides a high-level table view of all tracked DReps but lacks the ability to drill into an individual DRep's detailed profile. Users need a dedicated page per DRep to understand their governance participation, delegation metrics, and how their voting power has changed over time.

## 3. Goals

- Provide a single-page view of a DRep's key governance metrics
- Display voting power trends over time (by epoch)
- Show a complete, paginated vote history
- Link from the existing DRep table to each profile page

## 4. Non-Goals

- Editing or managing DRep data from the profile page
- Comparing two or more DReps side-by-side
- Social features (comments, ratings, following)
- Push notifications on DRep activity changes

## 5. User Stories

| # | As a... | I want to... | So that... |
|---|---------|-------------|------------|
| 1 | Dashboard user | Click a DRep name in the table and navigate to their profile | I can see detailed info without leaving the app |
| 2 | Dashboard user | See total votes, delegators, and voting power at a glance | I can quickly assess a DRep's influence and participation |
| 3 | Dashboard user | View a chart of voting power over time | I can identify trends in delegation to this DRep |
| 4 | Dashboard user | Browse the full vote history with pagination | I can audit how the DRep voted on each governance action |
| 5 | Dashboard user | Copy the DRep ID to clipboard | I can reference it in external tools or explorers |

## 6. Functional Requirements

### 6.1 Profile Header

- Display DRep name (or "Unnamed DRep" fallback)
- Display full DRep ID with a copy-to-clipboard button
- Show activity status badge (Active / Inactive / Inactive (Expired))
- Show registration epoch and date
- Link to off-chain metadata URL (if available)

### 6.2 Summary Statistics Cards

Three stat cards displayed in a row:

| Card | Value | Source |
|------|-------|--------|
| Total Votes | Count of votes cast by this DRep | `GET /api/dreps/{drep_id}/votes` (length or dedicated count) |
| Total Delegators | Current delegator count | `dreps.delegator_count` field |
| Total Voting Power | Current voting power in ADA | `dreps.total_voting_power` (convert from lovelace) |

### 6.3 Voting Power Over Time Chart

- Line chart (Chart.js) showing voting power (ADA) on the Y-axis and epoch on the X-axis
- Display up to the last 50 epochs of data
- Tooltip shows epoch number, voting power in ADA, and delegator count at that epoch
- **Requires new backend infrastructure** (see Section 8)

### 6.4 Vote History Table

- Paginated table (20 votes per page)
- Columns: Governance Action ID (truncated with tooltip for full ID), Vote (Yes/No/Abstain with color-coded badges), Voted Epoch
- Sorted by epoch descending (most recent first)
- Pagination controls (Previous / Next)

### 6.5 Navigation

- Add route `/dreps/:drepId` mapped to `DRepProfileView.vue`
- DRep names/IDs in `DRepTable.vue` and `DRepsView.vue` should be clickable links to the profile page
- Profile page should include a back link to the DReps list

## 7. Existing Components (In Progress)

Three Vue components already exist on the `feature/drep-profile-pages` branch as untracked files:

| Component | File | Status |
|-----------|------|--------|
| `DRepProfileView.vue` | `frontend/frontend-app/src/views/DRepProfileView.vue` | Shell created, needs route registration |
| `VoteHistoryTable.vue` | `frontend/frontend-app/src/components/VoteHistoryTable.vue` | Functional, paginated, sorted |
| `VotingPowerChart.vue` | `frontend/frontend-app/src/components/VotingPowerChart.vue` | Chart.js integration, expects snapshot data |

## 8. Technical Requirements

### 8.1 Backend Changes

#### New Database Table: `voting_power_snapshots`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| drep_id | String (FK → dreps.drep_id) | DRep identifier |
| epoch | Integer | Epoch number of the snapshot |
| voting_power | BigInteger | Voting power in lovelace at this epoch |
| delegator_count | Integer | Delegator count at this epoch |
| UNIQUE | | (drep_id, epoch) |

This table stores historical snapshots so the frontend can render voting power trends. Snapshots are recorded each time the scheduler updates DRep on-chain info (hourly check, stored per-epoch).

#### New API Endpoint

```
GET /api/dreps/{drep_id}/voting-power-history
Query params: limit (default 50), offset (default 0)
Response: List[VotingPowerSnapshot]
  - drep_id: str
  - epoch: int
  - voting_power: int  (lovelace)
  - delegator_count: int
```

#### Bug Fix

- `apiService.js` line 30: `getVotesByDrep()` references `drep_id` instead of `drepId` parameter — must be fixed.

### 8.2 Frontend Changes

#### Router (`router/index.js`)

Add dynamic route:

```javascript
{
  path: '/dreps/:drepId',
  name: 'drep-profile',
  component: () => import('../views/DRepProfileView.vue')
}
```

#### API Service (`apiService.js`)

Add method:

```javascript
getVotingPowerHistory(drepId, limit = 50, offset = 0) {
  return apiClient.get(`/dreps/${drepId}/voting-power-history`, {
    params: { limit, offset }
  });
}
```

Fix existing `getVotesByDrep()` bug (use `drepId` not `drep_id`).

#### DRep Table Link

Make DRep name/ID in `DRepTable.vue` a `<router-link>` to `/dreps/:drepId`.

### 8.3 Scheduler Change

During the hourly `update_drep_onchain_info_for_tracked()` job, after fetching current DRep info from Koios, insert or update a row in `voting_power_snapshots` for the current epoch with the latest `total_voting_power` and `delegator_count`.

## 9. Data Flow

```
User clicks DRep name in table
  → Router navigates to /dreps/:drepId
  → DRepProfileView.vue mounts
  → Parallel API calls:
      ├── GET /api/dreps/{drep_id}           → Header + stat cards
      ├── GET /api/dreps/{drep_id}/votes     → Vote history table
      └── GET /api/dreps/{drep_id}/voting-power-history → Chart data
  → Components render with fetched data
```

## 10. Unit Conversions

- Backend stores voting power in **lovelace** (1 ADA = 1,000,000 lovelace)
- Frontend converts to ADA for display: `voting_power / 1_000_000`
- Display with appropriate decimal places and "ADA" suffix

## 11. Edge Cases

| Case | Handling |
|------|----------|
| DRep not found (404) | Show error message with link back to DRep list |
| DRep has no votes | Show empty state in vote history ("No votes recorded") |
| No voting power history | Show empty chart with message ("No historical data available yet") |
| DRep has no name/metadata | Display "Unnamed DRep" with DRep ID |
| Very large voting power values | Format with locale-appropriate number separators |

## 12. Implementation Tasks

1. **Backend: Add `voting_power_snapshots` model and table migration**
2. **Backend: Record snapshots in scheduler during hourly DRep info sync**
3. **Backend: Add `GET /api/dreps/{drep_id}/voting-power-history` endpoint**
4. **Backend: Add Pydantic schema for `VotingPowerSnapshot`**
5. **Frontend: Register `/dreps/:drepId` route in router**
6. **Frontend: Fix `getVotesByDrep()` bug in `apiService.js`**
7. **Frontend: Add `getVotingPowerHistory()` to `apiService.js`**
8. **Frontend: Wire up `DRepProfileView.vue` with API calls and child components**
9. **Frontend: Add clickable links from DRep table rows to profile pages**
10. **Testing: Backend unit tests for new endpoint and snapshot logic**
11. **Testing: Frontend component tests for profile view**

## 13. Success Metrics

- Profile page loads all three data sections (header/stats, chart, vote history) within a single page load
- Voting power chart displays accurate historical data matching on-chain records
- Vote history is complete and matches data from Koios/backend
- Navigation between DRep list and profile pages works seamlessly

## 14. Dependencies

- **Chart.js** — already included in VotingPowerChart.vue
- **Koios API** — existing integration, no new endpoints needed from Koios
- **SQLite** — existing database, needs new table added via SQLAlchemy model
