import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx  # For fetching metadata_url
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import config, database, koios_api

logger = logging.getLogger(__name__)

IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://dweb.link/ipfs/",
]


def _normalize_metadata_url(url: str) -> str:
    """Convert ipfs:// scheme to an HTTP gateway URL."""
    if url.startswith("ipfs://"):
        cid = url[len("ipfs://"):]
        return IPFS_GATEWAYS[0] + cid
    return url


def _unwrap_value(v) -> Optional[str]:
    """Return v if it's a non-empty string, or v['@value'] if it's a JSON-LD value dict."""
    if isinstance(v, str):
        return v or None
    if isinstance(v, dict):
        inner = v.get("@value")
        return inner if isinstance(inner, str) and inner else None
    return None


def _extract_name_from_metadata_json(metadata_json: dict) -> Optional[str]:
    body = metadata_json.get("body") or {}
    return (
        _unwrap_value(metadata_json.get("name"))
        or _unwrap_value(metadata_json.get("bio", {}).get("name") if isinstance(metadata_json.get("bio"), dict) else None)
        or _unwrap_value(metadata_json.get("dRepName"))
        or _unwrap_value(body.get("dRepName"))
        or _unwrap_value(body.get("givenName"))
    )


async def _try_name_from_koios_updates(conn: Session, drep_id: str) -> None:
    """Try to derive a DRep name from Koios drep_updates meta_json as a fallback."""
    try:
        updates = await _call_koios_with_retry(koios_api.get_drep_updates, drep_id)
        if not updates:
            return
        # Sort by block_time descending, pick first with non-null meta_json
        updates_with_meta = [u for u in updates if u.get("meta_json")]
        if not updates_with_meta:
            return
        updates_with_meta.sort(key=lambda u: u.get("block_time") or 0, reverse=True)
        name = _extract_name_from_metadata_json(updates_with_meta[0]["meta_json"])
        if name and isinstance(name, str):
            drep_db_data = database.get_drep_by_id(conn, drep_id)
            if drep_db_data and not drep_db_data.get("name"):
                database.add_or_update_drep(conn, {"drep_id": drep_id, "name": name[:255]})
                logger.info(f"Derived name from Koios updates for {drep_id}: {name[:30]}")
    except Exception as e:
        logger.warning(f"Could not derive name from Koios updates for {drep_id}: {e}")


# Helper function for Koios API calls with retry
async def _call_koios_with_retry(api_func, *args, **kwargs):
    """
    Calls a Koios API function with retry logic for transient errors.
    """
    retries = config.KOIOS_RETRY_ATTEMPTS
    delay = config.KOIOS_RETRY_DELAY
    func_name = getattr(api_func, "__name__", None)
    if func_name is None:
        func_name = getattr(api_func, "_mock_name", repr(api_func))
    for attempt in range(retries):
        try:
            return await api_func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            if 400 <= e.response.status_code < 500:
                logger.warning(
                    f"Koios API call to {func_name} failed with client error {e.response.status_code}: {e}. No retry."
                )
                raise

            logger.warning(
                f"Koios API call to {func_name} failed (attempt {attempt + 1}/{retries}): {e}. Retrying in {delay}s..."
            )
        except httpx.RequestError as e:
            logger.warning(
                f"Koios API call to {func_name} failed (attempt {attempt + 1}/{retries}): {e}. Retrying in {delay}s..."
            )

        if attempt < retries - 1:
            await asyncio.sleep(delay)
            delay *= config.KOIOS_RETRY_BACKOFF_FACTOR
        else:
            logger.error(
                f"Koios API call to {func_name} failed after {retries} attempts."
            )
            raise
    return None


async def get_current_epoch():
    """Fetches the current epoch number from Koios with retry."""
    try:
        tip_info = await _call_koios_with_retry(koios_api.get_tip)
        if tip_info and isinstance(tip_info, list) and len(tip_info) > 0:
            epoch = tip_info[0].get("epoch_no")
            if epoch is not None:
                logger.info(f"Current epoch from Koios: {epoch}")
                return int(epoch)
            else:
                logger.warning(
                    "Could not extract 'epoch_no' from Koios /tip endpoint response."
                )
                return None
        logger.warning(
            f"Received unexpected or empty data from Koios /tip endpoint: {tip_info}"
        )
        return None
    except httpx.RequestError as e:
        logger.error(
            f"Could not fetch current epoch from Koios after retries: {e}",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while fetching current epoch: {e}",
            exc_info=True,
        )
        return None


def _timestamp_to_iso(timestamp: int | None) -> str | None:
    """Converts a UNIX timestamp to an ISO 8601 date string."""
    if timestamp is None:
        return None
    try:
        # Ensure timestamp is an integer or float
        return datetime.utcfromtimestamp(int(timestamp)).isoformat() + "Z"
    except (TypeError, ValueError) as e:
        logger.warning(f"Could not convert timestamp {timestamp} to ISO date: {e}")
        return None


def _determine_activity_status(
    drep_koios_data: dict, current_epoch: Optional[int]
) -> str:
    """Determines DRep activity status based on Koios data and current epoch."""
    is_active_koios = drep_koios_data.get("active", False)
    expires_epoch = drep_koios_data.get("expires_epoch_no")

    if is_active_koios:
        if current_epoch and expires_epoch and expires_epoch < current_epoch:
            return "Inactive (Expired)"
        return "Active"
    return "Inactive"


# --- DRep On-Chain Information Processing ---


async def _fetch_drep_bulk_koios_info(drep_ids: list[str]) -> dict:
    """
    Fetches DRep information from Koios in bulk for a list of DRep IDs.
    Handles chunking for large lists.
    Returns a map of drep_id to its Koios data.
    """
    all_drep_koios_data_map = {}
    if not drep_ids:
        return all_drep_koios_data_map

    logger.info(f"Fetching Koios bulk info for {len(drep_ids)} DRep ID(s).")
    for i in range(0, len(drep_ids), config.MAX_KOIOS_BULK_ITEMS):
        chunk = drep_ids[i : i + config.MAX_KOIOS_BULK_ITEMS]
        try:
            results = await _call_koios_with_retry(koios_api.get_drep_info, chunk)
            if results:
                for item in results:
                    if item.get("drep_id"):
                        all_drep_koios_data_map[item["drep_id"]] = item
        except httpx.RequestError as e:
            logger.error(
                f"Failed to fetch DRep info for chunk starting with {chunk[0] if chunk else 'N/A'} (size {len(chunk)}) after retries: {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching DRep info for chunk starting with {chunk[0] if chunk else 'N/A'}: {e}",
                exc_info=True,
            )
    return all_drep_koios_data_map


def _assemble_base_drep_data_from_koios(
    drep_id: str, drep_koios_data: dict, current_epoch: Optional[int]
) -> dict:
    """Assembles the base DRep data dictionary from Koios raw data."""
    return {
        "drep_id": drep_id,
        "metadata_url": drep_koios_data.get("meta_url"),
        "metadata_hash": drep_koios_data.get("meta_hash"),
        "total_voting_power": int(drep_koios_data.get("amount", 0)),
        "last_koios_update_epoch": current_epoch,
        "activity_status": _determine_activity_status(drep_koios_data, current_epoch),
        "registration_epoch": drep_koios_data.get("active_epoch_no"),  # May be None
        "expires_epoch_no": drep_koios_data.get("expires_epoch_no"),
    }


async def _fetch_and_set_drep_delegator_count(
    drep_id: str, drep_data_to_store: dict
) -> list[dict]:
    """Fetches DRep delegator count from Koios and updates drep_data_to_store.
    Returns the delegator list for reuse (e.g. CF delegation check)."""
    try:
        delegators_list = await _call_koios_with_retry(
            koios_api.get_drep_delegators, drep_id
        )
        delegators_list_result = delegators_list if delegators_list else []
        drep_data_to_store["delegator_count"] = len(delegators_list_result)
        logger.debug(
            f"Fetched {len(delegators_list_result)} delegators for DRep {drep_id}."
        )
        return delegators_list_result
    except httpx.RequestError as e:
        logger.error(
            f"Failed to fetch delegators for DRep {drep_id} after retries: {e}",
            exc_info=True,
        )
        return []
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while fetching delegators for DRep {drep_id}: {e}",
            exc_info=True,
        )
        return []


async def _fetch_and_set_detailed_drep_registration_date(
    drep_id: str, drep_data_to_store: dict, drep_in_db: Optional[dict]
) -> None:
    """
    Fetches DRep updates from Koios to determine and set a more precise registration date
    if conditions require it. Updates drep_data_to_store in place.
    """
    koios_active_epoch = drep_data_to_store.get(
        "registration_epoch"
    )  # Already set from drep_info

    needs_detailed_reg_date = not (drep_in_db and drep_in_db.get("registration_date"))
    # Also run when registration_epoch is still missing — needed to derive it from drep_updates
    if drep_data_to_store.get("registration_epoch") is None:
        needs_detailed_reg_date = True
    # Specific condition for DReps registered before Conway (epoch 540) that might have null active_epoch_no
    if (
        drep_in_db
        and drep_in_db.get("registration_epoch") is not None
        and drep_in_db.get("registration_epoch", 0) < 540
    ):
        if koios_active_epoch is None or koios_active_epoch < 540:
            needs_detailed_reg_date = True

    if needs_detailed_reg_date:
        logger.debug(
            f"Attempting to fetch detailed registration date for DRep {drep_id}."
        )
        try:
            updates = await _call_koios_with_retry(koios_api.get_drep_updates, drep_id)
            logger.info(f"DRep {drep_id}: Raw updates from /drep_updates: {updates}")
            if updates:
                updates_sorted = sorted(
                    updates, key=lambda x: x.get("block_time", float("inf"))
                )
                first_registration_action = next(
                    (u for u in updates_sorted if u.get("action") == "registered"), None
                )
                logger.info(
                    f"DRep {drep_id}: First registration action found: {first_registration_action is not None}"
                )

                reg_tx_hash = None
                if first_registration_action:
                    reg_tx_hash = first_registration_action.get(
                        "update_tx_hash"
                    )  # Corrected field name
                    logger.info(
                        f"DRep {drep_id}: Extracted registration tx_hash: {reg_tx_hash}"
                    )

                    # Set registration_date from block_time of the registration action, if available.
                    reg_block_time_from_updates = first_registration_action.get(
                        "block_time"
                    )
                    if reg_block_time_from_updates:
                        drep_data_to_store["registration_date"] = _timestamp_to_iso(
                            reg_block_time_from_updates
                        )
                        logger.info(
                            f"DRep {drep_id}: Set 'registration_date' to {drep_data_to_store['registration_date']} from /drep_updates block_time."
                        )
                        # Derive registration_epoch from block_time using Cardano mainnet Shelley formula
                        if drep_data_to_store.get("registration_epoch") is None:
                            SHELLEY_GENESIS_TIME = 1596491091
                            SHELLEY_START_EPOCH = 208
                            EPOCH_LENGTH_SECONDS = 432000
                            derived_epoch = SHELLEY_START_EPOCH + (reg_block_time_from_updates - SHELLEY_GENESIS_TIME) // EPOCH_LENGTH_SECONDS
                            drep_data_to_store["registration_epoch"] = derived_epoch
                            logger.info(
                                f"DRep {drep_id}: Derived 'registration_epoch' to {derived_epoch} from block_time."
                            )
                    else:
                        logger.warning(
                            f"DRep {drep_id}: No 'block_time' found in first_registration_action, 'registration_date' may not be set by this path."
                        )

                # New logic: Use get_tx_infos if registration_epoch is None and reg_tx_hash is available
                if drep_data_to_store.get("registration_epoch") is None and reg_tx_hash:
                    logger.info(
                        f"DRep {drep_id}: 'registration_epoch' is None. Attempting to derive from 'reg_tx_hash': {reg_tx_hash} using get_tx_infos."
                    )
                    try:
                        tx_info_list = await _call_koios_with_retry(
                            koios_api.get_tx_infos, [reg_tx_hash]
                        )
                        if (
                            tx_info_list
                            and isinstance(tx_info_list, list)
                            and len(tx_info_list) > 0
                        ):
                            tx_info = tx_info_list[0]
                            derived_epoch = tx_info.get("epoch_no")
                            tx_block_time = tx_info.get("tx_timestamp")

                            if derived_epoch is not None:
                                drep_data_to_store["registration_epoch"] = derived_epoch
                                logger.info(
                                    f"DRep {drep_id}: Successfully derived and set 'registration_epoch' to {derived_epoch} from get_tx_infos."
                                )
                            else:
                                logger.warning(
                                    f"DRep {drep_id}: 'epoch_no' not found in get_tx_infos response for {reg_tx_hash}."
                                )

                            if tx_block_time is not None:
                                new_reg_date = _timestamp_to_iso(tx_block_time)
                                if (
                                    drep_data_to_store.get("registration_date")
                                    != new_reg_date
                                ):
                                    logger.info(
                                        f"DRep {drep_id}: Updating 'registration_date' to {new_reg_date} from get_tx_infos (was {drep_data_to_store.get('registration_date')})."
                                    )
                                    drep_data_to_store["registration_date"] = (
                                        new_reg_date
                                    )
                                elif (
                                    drep_data_to_store.get("registration_date") is None
                                ):
                                    drep_data_to_store["registration_date"] = (
                                        new_reg_date
                                    )
                                    logger.info(
                                        f"DRep {drep_id}: Set 'registration_date' to {new_reg_date} from get_tx_infos."
                                    )
                            else:
                                logger.warning(
                                    f"DRep {drep_id}: 'tx_timestamp' not found in get_tx_infos response for {reg_tx_hash}. 'registration_date' might rely on /drep_updates."
                                )

                        else:
                            logger.warning(
                                f"DRep {drep_id}: get_tx_infos call for {reg_tx_hash} returned no data or failed."
                            )
                    except httpx.RequestError as re:
                        logger.error(
                            f"DRep {drep_id}: Koios API request failed during get_tx_infos for {reg_tx_hash}: {re}",
                            exc_info=True,
                        )
                    except Exception as ex:
                        logger.error(
                            f"DRep {drep_id}: Unexpected error using get_tx_infos for {reg_tx_hash}: {ex}",
                            exc_info=True,
                        )

                elif drep_data_to_store.get("registration_epoch") is None:
                    logger.warning(
                        f"DRep {drep_id}: 'registration_epoch' is None, and 'reg_tx_hash' was not available from DRep updates to attempt derivation with get_tx_infos."
                    )

            else:
                logger.info(
                    f"DRep {drep_id}: No 'registered' action or no updates found. Cannot determine registration details from /drep_updates."
                )

        except httpx.RequestError as e:
            logger.error(
                f"Failed to fetch DRep updates for {drep_id} for detailed registration date after retries: {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching DRep updates for {drep_id}: {e}",
                exc_info=True,
            )


async def _process_single_drep_onchain_info(
    conn: Session,
    drep_id: str,
    drep_koios_data: dict,
    current_epoch: Optional[int],
) -> None:
    """
    Processes and stores on-chain information for a single DRep.
    """
    logger.debug(f"Processing DRep on-chain data for: {drep_id}")

    drep_data_to_store = _assemble_base_drep_data_from_koios(
        drep_id, drep_koios_data, current_epoch
    )

    delegators = await _fetch_and_set_drep_delegator_count(drep_id, drep_data_to_store)

    # Extract CF delegation from already-fetched delegators (avoids duplicate API call)
    cf_stake_addresses = getattr(config, "CF_STAKE_ADDRESSES", [])
    if cf_stake_addresses and delegators:
        cf_total_lovelace = sum(
            int(d.get("amount", 0))
            for d in delegators
            if d.get("stake_address") in cf_stake_addresses
        )
        if cf_total_lovelace > 0:
            drep_data_to_store["cf_delegated_ada"] = cf_total_lovelace // 1_000_000

    drep_in_db = None
    try:
        drep_in_db = database.get_drep_by_id(conn, drep_id)
    except SQLAlchemyError as e_db:
        logger.error(
            f"Database error fetching DRep {drep_id} details: {e_db}", exc_info=True
        )

    await _fetch_and_set_detailed_drep_registration_date(
        drep_id, drep_data_to_store, drep_in_db
    )

    # Never overwrite good data with nulls from transient API responses
    PRESERVE_FIELDS = ["registration_epoch", "total_voting_power", "cf_delegated_ada"]
    if drep_in_db:
        for field in PRESERVE_FIELDS:
            if drep_data_to_store.get(field) is None and drep_in_db.get(field) is not None:
                del drep_data_to_store[field]

    # Fallback: derive registration_epoch from earliest vote if still missing
    if drep_data_to_store.get("registration_epoch") is None:
        earliest = database.get_earliest_vote_epoch(conn, drep_id)
        if earliest is not None:
            drep_data_to_store["registration_epoch"] = earliest
            logger.info(
                f"DRep {drep_id}: Derived registration_epoch={earliest} from earliest vote."
            )

    try:
        database.add_or_update_drep(conn, drep_data_to_store)
        logger.info(f"Stored/Updated DRep on-chain info for: {drep_id}")
    except SQLAlchemyError as e_db:
        logger.error(
            f"Database error storing/updating DRep on-chain info for {drep_id}: {e_db}",
            exc_info=True,
        )

    # Record voting power snapshot for the current epoch
    if current_epoch is not None:
        try:
            database.add_or_update_voting_power_snapshot(
                conn,
                drep_id=drep_id,
                epoch=current_epoch,
                voting_power=drep_data_to_store.get("total_voting_power", 0),
                delegator_count=drep_data_to_store.get("delegator_count", 0),
            )
            logger.info(
                f"Recorded voting power snapshot for DRep {drep_id} at epoch {current_epoch}."
            )
        except SQLAlchemyError as e_db:
            logger.error(
                f"Database error recording voting power snapshot for {drep_id} at epoch {current_epoch}: {e_db}",
                exc_info=True,
            )


async def process_and_store_drep_info(conn: Session, drep_ids: list[str]):
    """
    Fetches DRep information from Koios for a list of DRep IDs, processes it,
    and stores/updates it in the database.
    """
    if not drep_ids:
        logger.info("No DRep IDs provided to process_and_store_drep_info.")
        return

    current_epoch = await get_current_epoch()
    logger.info(
        f"Processing DRep on-chain info for {len(drep_ids)} DRep(s). Current epoch: {current_epoch}"
    )

    all_drep_koios_data_map = await _fetch_drep_bulk_koios_info(drep_ids)

    for drep_id in drep_ids:
        drep_koios_data = all_drep_koios_data_map.get(drep_id)

        if not drep_koios_data:
            logger.warning(
                f"No info found from Koios for DRep: {drep_id}. Updating status and epoch."
            )
            try:
                database.add_or_update_drep(
                    conn,
                    {
                        "drep_id": drep_id,
                        "activity_status": "Error Fetching Info",
                        "last_koios_update_epoch": current_epoch,
                    },
                )
            except SQLAlchemyError as e_db:
                logger.error(
                    f"Database error updating DRep {drep_id} status to 'Error Fetching Info': {e_db}",
                    exc_info=True,
                )
            await asyncio.sleep(0.1)
            continue

        await _process_single_drep_onchain_info(
            conn, drep_id, drep_koios_data, current_epoch
        )
        await asyncio.sleep(config.KOIOS_API_CALL_DELAY_SECONDS)


async def update_drep_onchain_info_for_tracked(conn: Session):
    """Wrapper to call process_and_store_drep_info for all tracked DReps."""
    logger.info("Starting job: update_drep_onchain_info_for_tracked")
    tracked_drep_ids_list = []
    try:
        tracked_drep_ids_list = database.get_tracked_drep_ids(conn)
    except SQLAlchemyError as e_db:
        logger.error(
            f"Database error fetching tracked DRep IDs: {e_db}. Aborting on-chain info update.",
            exc_info=True,
        )
        return

    if not tracked_drep_ids_list:
        logger.info(
            "No DReps are currently being tracked. Skipping on-chain info update."
        )
        return
    await process_and_store_drep_info(conn, tracked_drep_ids_list)
    logger.info("Finished job: update_drep_onchain_info_for_tracked")


async def update_drep_offchain_metadata_for_tracked(conn: Session):
    """Fetches and updates off-chain metadata for tracked DReps."""
    logger.info("Starting job: update_drep_offchain_metadata_for_tracked")
    tracked_drep_ids_for_metadata = []
    try:
        tracked_drep_ids_for_metadata = database.get_tracked_drep_ids(conn)
    except SQLAlchemyError as e_db:
        logger.error(
            f"Database error fetching tracked DRep IDs for metadata update: {e_db}. Aborting metadata update.",
            exc_info=True,
        )
        return

    if not tracked_drep_ids_for_metadata:
        logger.info("No DReps are currently being tracked for metadata update.")
        return

    logger.info(
        f"Updating off-chain metadata for {len(tracked_drep_ids_for_metadata)} DReps."
    )

    async with httpx.AsyncClient(timeout=config.REQUESTS_TIMEOUT, follow_redirects=True) as client:
        for drep_id in tracked_drep_ids_for_metadata:
            drep_db_data = None
            try:
                drep_db_data = database.get_drep_by_id(conn, drep_id)
            except SQLAlchemyError as e_db:
                logger.error(
                    f"Database error fetching DRep {drep_id} for metadata update: {e_db}. Skipping this DRep.",
                    exc_info=True,
                )
                continue

            if not drep_db_data:
                logger.warning(
                    f"Tracked DRep {drep_id} not found in dreps table (or DB error occurred). Skipping metadata update."
                )
                continue

            metadata_url = drep_db_data.get("metadata_url")
            expected_hash = drep_db_data.get("metadata_hash")
            current_time_iso = datetime.now(timezone.utc).isoformat()

            if not metadata_url or not expected_hash:
                logger.debug(
                    f"Skipping metadata check for {drep_id}: no URL or hash in DB."
                )
                try:
                    database.update_drep_metadata_status(
                        conn, drep_id, "Missing Info", current_time_iso
                    )
                except SQLAlchemyError as e_db:
                    logger.error(
                        f"Database error updating metadata status for {drep_id} (Missing Info): {e_db}",
                        exc_info=True,
                    )
                await asyncio.sleep(0.1)
                continue

            status = "Error Fetching"
            try:
                fetch_url = _normalize_metadata_url(metadata_url)
                logger.info(f"Fetching metadata for {drep_id} from {fetch_url}")
                req_headers = {
                    "User-Agent": "DRepTracker/1.0 (cardano-community/drep-tracker)"
                }

                response = await client.get(fetch_url, headers=req_headers)
                response.raise_for_status()

                fetched_content = response.content
                blake2b_hash_obj = hashlib.blake2b(digest_size=32)
                blake2b_hash_obj.update(fetched_content)
                actual_hash_blake2b = blake2b_hash_obj.hexdigest()

                if actual_hash_blake2b == expected_hash:
                    status = "Match"
                    logger.info(f"Metadata for {drep_id} matches expected hash.")
                    if (
                        not drep_db_data.get("name")
                        or drep_db_data.get("name") == "Name N/A"
                    ):
                        try:
                            metadata_json = response.json()
                            drep_name = _extract_name_from_metadata_json(metadata_json)
                            if drep_name:
                                try:
                                    database.add_or_update_drep(
                                        conn,
                                        {"drep_id": drep_id, "name": drep_name[:255]},
                                    )
                                    logger.info(
                                        f"Updated name for DRep {drep_id} from metadata: {drep_name[:30]}..."
                                    )
                                except SQLAlchemyError as e_db:
                                    logger.error(
                                        f"Database error updating DRep name for {drep_id}: {e_db}",
                                        exc_info=True,
                                    )
                        except Exception as json_e:
                            logger.warning(
                                f"Could not parse metadata JSON or extract name for {drep_id} (URL: {metadata_url}): {json_e}"
                            )
                else:
                    status = "Mismatch"
                    logger.warning(
                        f"Metadata hash mismatch for {drep_id}. Expected: {expected_hash}, Got: {actual_hash_blake2b}. URL: {metadata_url}"
                    )

            except httpx.HTTPStatusError as http_err:
                logger.error(
                    f"HTTP error fetching metadata for {drep_id} from {fetch_url}: {http_err.response.status_code} - {http_err.response.text[:100]}"
                )
                status = f"Error Fetching: HTTP {http_err.response.status_code}"
                await _try_name_from_koios_updates(conn, drep_id)
            except httpx.RequestError as req_err:
                logger.error(
                    f"Request error fetching metadata for {drep_id} from {fetch_url}: {req_err}"
                )
                # Retry with fallback IPFS gateways if applicable
                if "/ipfs/" in fetch_url:
                    cid = fetch_url.split("/ipfs/", 1)[1]
                    for gateway in IPFS_GATEWAYS[1:]:
                        fallback_url = gateway + cid
                        try:
                            logger.info(f"Retrying IPFS fetch for {drep_id} via {fallback_url}")
                            response = await client.get(fallback_url, headers=req_headers)
                            response.raise_for_status()
                            fetched_content = response.content
                            blake2b_hash_obj = hashlib.blake2b(digest_size=32)
                            blake2b_hash_obj.update(fetched_content)
                            actual_hash_blake2b = blake2b_hash_obj.hexdigest()
                            if actual_hash_blake2b == expected_hash:
                                status = "Match"
                                logger.info(f"Metadata for {drep_id} matches via IPFS fallback {fallback_url}.")
                                if not drep_db_data.get("name") or drep_db_data.get("name") == "Name N/A":
                                    try:
                                        metadata_json = response.json()
                                        drep_name = _extract_name_from_metadata_json(metadata_json)
                                        if drep_name and isinstance(drep_name, str):
                                            database.add_or_update_drep(conn, {"drep_id": drep_id, "name": drep_name[:255]})
                                    except Exception:
                                        pass
                            else:
                                status = "Mismatch"
                            break
                        except Exception:
                            continue
                    else:
                        status = f"Error Fetching: {type(req_err).__name__}"
                        await _try_name_from_koios_updates(conn, drep_id)
                else:
                    status = f"Error Fetching: {type(req_err).__name__}"
                    await _try_name_from_koios_updates(conn, drep_id)
            except hashlib.error as hash_err:
                logger.error(
                    f"Error calculating hash for metadata of {drep_id} from {fetch_url}: {hash_err}"
                )
                status = "Error Processing: Hash Calc Failed"
            except Exception as e:
                logger.error(
                    f"Generic error processing metadata for {drep_id} from {fetch_url}: {e}",
                    exc_info=True,
                )
                status = "Error Processing"

            try:
                database.update_drep_metadata_status(
                    conn, drep_id, status, current_time_iso
                )
            except SQLAlchemyError as e_db:
                logger.error(
                    f"Database error updating metadata status for {drep_id} (Status: {status}): {e_db}",
                    exc_info=True,
                )

            await asyncio.sleep(0.5)

    logger.info("Finished job: update_drep_offchain_metadata_for_tracked")


# --- Governance Action and Vote Processing ---


def _prepare_ga_data_for_db(proposal_from_api: dict) -> Optional[dict]:
    """
    Prepares governance action data from Koios API response for database insertion.
    """
    ga_id_koios = proposal_from_api.get("proposal_id")
    tx_hash = proposal_from_api.get("proposal_tx_hash")
    cert_index = proposal_from_api.get("proposal_index")

    if not ga_id_koios:
        if tx_hash and cert_index is not None:
            ga_id_koios = f"{tx_hash}_{cert_index}"
            logger.warning(
                f"Proposal missing 'proposal_id' (bech32), constructed ID {ga_id_koios}. Vote fetching may be affected."
            )
        else:
            logger.warning(
                f"Skipping proposal due to missing 'proposal_id' and essential construction fields (tx_hash, cert_index): {proposal_from_api}"
            )
            return None

    meta_json_data = proposal_from_api.get("meta_json")
    title_to_set = "Title N/A"

    if isinstance(meta_json_data, dict):
        body_data = meta_json_data.get("body")
        if isinstance(body_data, dict):
            title_candidate = body_data.get("title")
            if title_candidate is not None:
                title_to_set = str(title_candidate)

    return {
        "ga_id": ga_id_koios,
        "title": title_to_set,
        "type": proposal_from_api.get("proposal_type"),
        "submission_epoch": proposal_from_api.get("proposed_epoch"),
        "submission_date": _timestamp_to_iso(proposal_from_api.get("block_time")),
        "expiration_epoch": proposal_from_api.get("expiration"),
        "expiration_date": None,
        "tx_hash": tx_hash,
        "cert_index": cert_index,
    }


def _should_fetch_votes_for_ga(
    conn: Session,
    ga_id: str,
    proposal_from_api: dict,
    existing_ga_in_db: Optional[dict],
    current_epoch: int,
) -> bool:
    """
    Determines if votes for a given governance action should be fetched.
    """
    if not existing_ga_in_db:
        logger.info(f"New governance action found: {ga_id}. Will fetch votes.")
        return True

    try:
        vote_count = database.get_vote_count_for_ga(conn, ga_id)
    except SQLAlchemyError as e_db:
        logger.error(
            f"Database error checking existing votes for GA {ga_id}: {e_db}",
            exc_info=True,
        )
        vote_count = 0

    if vote_count == 0:
        logger.debug(
            f"GA {ga_id} has no votes stored in DB. Will fetch votes regardless of age."
        )
        return True

    is_concluded = (
        proposal_from_api.get("ratified_epoch")
        or proposal_from_api.get("enacted_epoch")
        or proposal_from_api.get("dropped_epoch")
    )

    ga_expiration_epoch = proposal_from_api.get("expiration")
    ga_submission_epoch = proposal_from_api.get("proposed_epoch")

    if not is_concluded:
        if ga_expiration_epoch and current_epoch <= ga_expiration_epoch:
            logger.debug(
                f"GA {ga_id} is existing, not concluded, and not expired. Queued for vote update."
            )
            return True
        if (
            not ga_expiration_epoch
            and ga_submission_epoch
            and ga_submission_epoch >= (current_epoch - config.GA_RECENCY_EPOCH_WINDOW)
        ):
            logger.debug(
                f"GA {ga_id} is existing, not concluded, no expiration epoch, but submitted recently. Queued for vote update."
            )
            return True
        if not ga_expiration_epoch and not ga_submission_epoch:
            logger.debug(
                f"GA {ga_id} is existing, not concluded, and has no epoch info. Defaulting to fetch votes."
            )
            return True
    elif ga_submission_epoch and ga_submission_epoch >= (
        current_epoch - config.GA_RECENCY_EPOCH_WINDOW
    ):
        logger.debug(
            f"GA {ga_id} is existing, possibly concluded, but submitted recently. Queued for vote update."
        )
        return True

    logger.debug(
        f"GA {ga_id} exists but is considered old/concluded. Skipping vote refresh for this run."
    )
    return False


def _ensure_drep_exists_for_vote(
    conn: Session, drep_id: str, ga_id_for_log: str
) -> bool:
    """
    Checks if a DRep exists in the database. If not, attempts to add a minimal entry.
    """
    try:
        if database.get_drep_by_id(conn, drep_id):
            return True

        logger.info(
            f"DRep {drep_id} from vote on GA {ga_id_for_log} not in 'dreps' table. Adding minimal entry."
        )
        database.add_or_update_drep(conn, {"drep_id": drep_id})
        return True
    except SQLAlchemyError as e_db:
        logger.error(
            f"Database error ensuring DRep {drep_id} existence for vote on GA {ga_id_for_log}: {e_db}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error ensuring DRep {drep_id} for vote on GA {ga_id_for_log}: {e}",
            exc_info=True,
        )
        return False


def _process_and_store_single_vote(
    conn: Session, vote_from_api: dict, ga_id: str
) -> None:
    """Processes a single vote from the API and stores it in the database."""
    drep_id_from_vote = vote_from_api.get("voter_id")

    if vote_from_api.get("voter_role") != "DRep":
        logger.debug(
            f"Skipping non-DRep vote for GA {ga_id} by {drep_id_from_vote} (Role: {vote_from_api.get('voter_role')})"
        )
        return

    if not drep_id_from_vote:
        logger.warning(
            f"Skipping vote due to missing 'voter_id' on GA {ga_id}: {vote_from_api}"
        )
        return

    if not _ensure_drep_exists_for_vote(conn, drep_id_from_vote, ga_id):
        logger.warning(
            f"Skipping vote by DRep {drep_id_from_vote} on GA {ga_id} because DRep could not be added/verified in DB."
        )
        return

    meta_url = vote_from_api.get("meta_url")
    vote_data_for_db = {
        "drep_id": drep_id_from_vote,
        "ga_id": ga_id,
        "vote": vote_from_api.get("vote"),
        "voted_epoch": vote_from_api.get("epoch_no"),
        "has_rationale": 1 if meta_url else 0,
        "vote_anchor_url": meta_url,
    }
    try:
        database.add_drep_vote(conn, vote_data_for_db)
    except SQLAlchemyError as e_db_vote:
        logger.error(
            f"Database error adding vote for DRep {drep_id_from_vote} on GA {ga_id}: {e_db_vote}",
            exc_info=True,
        )


async def _fetch_and_store_votes_for_ga_list(
    conn: Session, ga_ids_to_fetch_votes_for: list[str]
):
    """Fetches and stores votes from Koios for a list of governance action IDs."""
    if not ga_ids_to_fetch_votes_for:
        logger.info("No governance actions require vote fetching in this run.")
        return

    logger.info(
        f"Attempting to fetch votes for {len(ga_ids_to_fetch_votes_for)} governance actions."
    )
    for ga_id_to_process in ga_ids_to_fetch_votes_for:
        votes_from_api = None
        try:
            votes_from_api = await _call_koios_with_retry(
                koios_api.get_proposal_votes, ga_id_to_process
            )
            if votes_from_api is not None:
                logger.info(
                    f"Fetched {len(votes_from_api)} votes for GA {ga_id_to_process}."
                )
        except httpx.RequestError as e:
            logger.error(
                f"Failed to fetch votes for GA {ga_id_to_process} after retries: {e}",
                exc_info=True,
            )
            continue
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching votes for GA {ga_id_to_process}: {e}",
                exc_info=True,
            )
            continue

        if votes_from_api is None:
            logger.warning(
                f"Votes list is None for GA {ga_id_to_process} (fetch might have failed silently or no votes). Skipping vote processing."
            )
            continue

        for vote_item in votes_from_api:
            _process_and_store_single_vote(conn, vote_item, ga_id_to_process)

        await asyncio.sleep(config.KOIOS_API_CALL_DELAY_SECONDS)
    logger.info(
        "Finished fetching and storing votes for the selected governance actions."
    )


async def fetch_recent_governance_actions_and_votes(conn: Session):
    """
    Fetches recent governance actions from Koios, stores them,
    and then fetches and stores votes for new or relevant GAs.
    """
    logger.info("Starting job: fetch_recent_governance_actions_and_votes")
    current_epoch = await get_current_epoch()
    if current_epoch is None:
        logger.error(
            "Could not determine current epoch after retries. Aborting GA update."
        )
        return

    proposals_from_api = None
    try:
        proposals_from_api = await _call_koios_with_retry(koios_api.get_proposal_list)
    except httpx.RequestError as e:
        logger.error(
            f"Failed to fetch proposal list from Koios after retries: {e}",
            exc_info=True,
        )
        return
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while fetching proposal list: {e}",
            exc_info=True,
        )
        return

    if not proposals_from_api:
        logger.info(
            "No governance actions/proposals returned from Koios or fetch failed."
        )
        return
    logger.info(
        f"Fetched {len(proposals_from_api)} total governance actions from Koios."
    )

    ga_ids_to_fetch_votes_for = []
    processed_ga_for_votes_count = 0

    for proposal_api_data in proposals_from_api:
        if proposal_api_data is None:
            logger.warning(
                "Encountered a None item in proposals_from_api list during iteration. Skipping this item."
            )
            continue

        logger.debug(
            f"About to process proposal_api_data for _prepare_ga_data_for_db: {proposal_api_data}"
        )
        ga_data_for_db = _prepare_ga_data_for_db(proposal_api_data)
        if not ga_data_for_db:
            continue

        ga_id = ga_data_for_db["ga_id"]
        existing_ga_in_db = None
        try:
            existing_ga_in_db = database.get_ga_by_id(conn, ga_id)
            database.add_governance_action(conn, ga_data_for_db)
        except SQLAlchemyError as e_db:
            logger.error(
                f"Database error processing GA {ga_id}: {e_db}. Skipping this GA.",
                exc_info=True,
            )
            continue

        if _should_fetch_votes_for_ga(
            conn, ga_id, proposal_api_data, existing_ga_in_db, current_epoch
        ):
            if (
                config.MAX_PROPOSALS_TO_PROCESS_INITIALLY == 0
                or len(ga_ids_to_fetch_votes_for)
                < config.MAX_PROPOSALS_TO_PROCESS_INITIALLY
            ):
                ga_ids_to_fetch_votes_for.append(ga_id)
            elif (
                len(ga_ids_to_fetch_votes_for)
                == config.MAX_PROPOSALS_TO_PROCESS_INITIALLY
                and config.MAX_PROPOSALS_TO_PROCESS_INITIALLY > 0
                and processed_ga_for_votes_count == 0
            ):
                logger.info(
                    f"MAX_PROPOSALS_TO_PROCESS_INITIALLY ({config.MAX_PROPOSALS_TO_PROCESS_INITIALLY}) reached for vote fetching. No more GAs will have votes fetched this run."
                )
                processed_ga_for_votes_count = -1

    if (
        processed_ga_for_votes_count != -1
        and config.MAX_PROPOSALS_TO_PROCESS_INITIALLY > 0
        and len(ga_ids_to_fetch_votes_for) >= config.MAX_PROPOSALS_TO_PROCESS_INITIALLY
    ):
        logger.info(
            f"Vote fetching will be limited to the first {config.MAX_PROPOSALS_TO_PROCESS_INITIALLY} identified recent/new GAs."
        )

    await _fetch_and_store_votes_for_ga_list(conn, ga_ids_to_fetch_votes_for)
    logger.info("Finished job: fetch_recent_governance_actions_and_votes.")


# --- Utility and Main Execution ---


async def update_tracked_dreps_full_info(conn):
    """
    Fetches and updates both on-chain and off-chain metadata for all tracked DReps.
    """
    logger.info("Starting full update for tracked DReps (on-chain and off-chain).")
    await update_drep_onchain_info_for_tracked(conn)
    await update_drep_offchain_metadata_for_tracked(conn)
    logger.info("Finished full update for tracked DReps.")


def get_active_dreps() -> list[dict]:
    """Returns all DReps with activity_status 'Active'."""
    db = database.get_db_connection()
    try:
        stmt = select(database.models.DRep).where(
            database.models.DRep.activity_status == "Active"
        )
        dreps = db.scalars(stmt).all()
        return [
            {c.name: getattr(d, c.name) for c in database.models.DRep.__table__.columns}
            for d in dreps
        ]
    finally:
        db.close()


def get_voting_power_per_drep() -> pd.DataFrame:
    """Returns voting power per DRep as a DataFrame."""
    return pd.read_sql_query(
        "SELECT drep_id, total_voting_power FROM dreps ORDER BY total_voting_power DESC",
        database.engine,
    )


async def update_cf_delegation_amounts(conn: Session):
    """
    For each tracked DRep, check if CF stake addresses are among their delegators.
    Updates cf_delegated_ada on the DRep record.
    """
    from . import config as cfg

    cf_stake_addresses = getattr(cfg, "CF_STAKE_ADDRESSES", [])
    if not cf_stake_addresses:
        logger.debug("No CF_STAKE_ADDRESSES configured; skipping CF delegation update.")
        return

    tracked_ids = database.get_tracked_drep_ids(conn)
    if not tracked_ids:
        logger.info("No tracked DReps to update CF delegation amounts for.")
        return

    # Fetch current epoch once for setting delegation_epoch
    current_epoch = await get_current_epoch()

    logger.info(
        f"Updating CF delegation amounts for {len(tracked_ids)} tracked DReps."
    )
    for drep_id in tracked_ids:
        try:
            delegators = await _call_koios_with_retry(
                koios_api.get_drep_delegators, drep_id
            )
            if not delegators:
                continue

            cf_total_lovelace = 0
            for delegator in delegators:
                stake_addr = delegator.get("stake_address")
                if stake_addr and stake_addr in cf_stake_addresses:
                    amount = int(delegator.get("amount", 0))
                    cf_total_lovelace += amount

            if cf_total_lovelace > 0:
                cf_ada = cf_total_lovelace // 1_000_000
                drep = database.get_drep_by_id(conn, drep_id)
                if drep:
                    update_data = {"drep_id": drep_id, "cf_delegated_ada": cf_ada}
                    # Only set delegation_epoch if not already set (preserve first delegation epoch for tenure)
                    if not drep.get("delegation_epoch"):
                        update_data["delegation_epoch"] = current_epoch
                    database.add_or_update_drep(conn, update_data)
                    logger.info(
                        f"DRep {drep_id}: CF delegated {cf_ada} ADA."
                    )

            await asyncio.sleep(config.KOIOS_API_CALL_DELAY_SECONDS)
        except Exception as e:
            logger.error(
                f"Error updating CF delegation for DRep {drep_id}: {e}",
                exc_info=True,
            )


def get_votes_matrix() -> pd.DataFrame:
    """Returns DRep votes versus governance actions as a matrix."""
    try:
        dreps = pd.read_sql_query("SELECT drep_id FROM tracked_dreps", database.engine)[
            "drep_id"
        ].tolist()
        ga_ids = pd.read_sql_query(
            "SELECT ga_id FROM governance_actions", database.engine
        )["ga_id"].tolist()
        df = pd.DataFrame("–", index=dreps, columns=ga_ids)
        votes = pd.read_sql_query(
            "SELECT drep_id, ga_id, vote FROM drep_votes", database.engine
        )
        for _, row in votes.iterrows():
            if row["drep_id"] in df.index and row["ga_id"] in df.columns:
                df.at[row["drep_id"], row["ga_id"]] = row["vote"]
        return df
    except Exception as e:
        logger.error(f"Error generating votes matrix: {e}")
        return pd.DataFrame()


def sync_initial_dreps_to_tracked_list(conn):
    """Adds DReps from config.INITIAL_DREP_LIST to the tracked_dreps table."""
    logger.info(
        f"Syncing INITIAL_DREP_LIST to tracked_dreps table: {config.INITIAL_DREP_LIST}"
    )
    for drep_id in config.INITIAL_DREP_LIST:
        try:
            database.add_tracked_drep(conn, drep_id)
        except SQLAlchemyError as e_db:
            logger.error(
                f"Database error syncing DRep {drep_id} to tracked list: {e_db}",
                exc_info=True,
            )
    logger.info("Finished syncing INITIAL_DREP_LIST.")


if __name__ == "__main__":
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=config.LOG_LEVEL,
            format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )

    logger.info("--- Testing Data Manager Functions (as __main__) ---")

    database.create_tables_if_not_exist()
    db_connection = database.get_db_connection()

    if db_connection is None:
        logger.error(
            "Could not establish database connection for data_manager testing."
        )
    else:
        try:
            logger.info("DB Connection successful for testing.")

            logger.info("\nTesting sync_initial_dreps_to_tracked_list...")
            sync_initial_dreps_to_tracked_list(db_connection)

            logger.info("\nTesting update_drep_onchain_info_for_tracked...")
            asyncio.run(update_drep_onchain_info_for_tracked(db_connection))

            logger.info("\nTesting update_drep_offchain_metadata_for_tracked...")
            asyncio.run(update_drep_offchain_metadata_for_tracked(db_connection))

            logger.info("\nTesting fetch_recent_governance_actions_and_votes...")
            asyncio.run(fetch_recent_governance_actions_and_votes(db_connection))

            logger.info("\n--- Data Manager Tests Complete ---")

        except AssertionError as ae:
            logger.error(
                f"Assertion failed during data_manager testing: {ae}", exc_info=True
            )
        except Exception as e:
            logger.error(
                f"An error occurred during data_manager testing: {e}", exc_info=True
            )
        finally:
            if db_connection:
                db_connection.close()
                logger.info("Database connection closed after data_manager tests.")
