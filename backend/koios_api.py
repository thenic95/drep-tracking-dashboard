import asyncio
import logging
from typing import Optional

import httpx

from . import config  # Assuming config.py is in the same directory

# Configure logging
# logging.basicConfig(level=config.LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)  # Ensure logger respects config level

COMMON_HEADERS = {
    "Authorization": f"Bearer {config.KOIOS_API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


async def _make_request(
    method, endpoint_suffix, params=None, json_data=None, headers=None
):
    """Helper function to make asynchronous HTTP requests to Koios API using httpx."""
    url = f"{config.KOIOS_API_BASE_URL}{endpoint_suffix}"
    actual_headers = headers if headers else COMMON_HEADERS

    logger.debug(
        f"Making {method} request to {url} with params: {params}, json: {json_data}"
    )
    async with httpx.AsyncClient(timeout=config.REQUESTS_TIMEOUT) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=actual_headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(
                    url, headers=actual_headers, json=json_data
                )
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()  # Raises for 4XX or 5XX status codes

            # Handle cases where response might be empty or not JSON
            if response.status_code == 204:  # No Content
                return []
            if not response.content:  # Empty response body
                return []

            try:
                return response.json()
            except Exception:  # httpx raises different errors than requests
                logger.error(
                    f"Failed to decode JSON from response. URL: {url}, Status: {response.status_code}, Response Text: {response.text[:500]}"
                )
                # Depending on strictness, could return None, [], or raise an error
                return []  # Or raise custom error

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error occurred: {e} - URL: {url} - Status: {e.response.status_code} - Response: {e.response.text[:500]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"An error occurred during the request: {e} - URL: {url}")
            raise


async def get_drep_info(drep_ids: list[str]) -> list[dict]:
    """Fetches data from POST /drep_info for a list of DRep IDs."""
    if not drep_ids:
        return []

    # Koios API might have a limit on the number of items in a bulk request.
    # Chunking the drep_ids if necessary.
    all_results = []
    for i in range(0, len(drep_ids), config.MAX_KOIOS_BULK_ITEMS):
        chunk = drep_ids[i : i + config.MAX_KOIOS_BULK_ITEMS]
        payload = {"_drep_ids": chunk}
        try:
            results = await _make_request("POST", "/drep_info", json_data=payload)
            if results:  # Ensure results is not None
                all_results.extend(results)
        except Exception as e:
            logger.error(f"Error fetching DRep info for chunk {chunk}: {e}")
            # Decide if one chunk failure should stop all or just skip this chunk
            # For now, log and continue
    return all_results


async def get_tx_infos(tx_hashes: list[str]) -> list[dict]:
    """Fetches data from POST /tx_info for a list of transaction hashes."""
    if not tx_hashes:
        return []

    all_results = []
    for i in range(0, len(tx_hashes), config.MAX_KOIOS_BULK_ITEMS):
        chunk = tx_hashes[i : i + config.MAX_KOIOS_BULK_ITEMS]
        payload = {"_tx_hashes": chunk}
        try:
            results = await _make_request("POST", "/tx_info", json_data=payload)
            # _make_request is expected to return a list. If results is None or not a list,
            # it might indicate an issue not caught by _make_request's exception handling,
            # or a valid empty response (e.g. 204 No Content, though /tx_info likely returns data or 404).
            if results and isinstance(results, list):
                all_results.extend(results)
            elif results is not None:  # Received something but not a list
                logger.warning(
                    f"Received non-list data from /tx_info for chunk {chunk}: {results}"
                )
        except Exception as e:
            logger.error(f"Error fetching transaction info for chunk {chunk}: {e}")
            # Decide if one chunk failure should stop all or just skip this chunk
            # For now, log and continue, similar to get_drep_info
    # Each item in all_results should be a dictionary.
    # Koios /tx_info returns 'epoch_no' and 'tx_timestamp' (which serves as 'block_time').
    return all_results


async def get_drep_updates(drep_id: str) -> list[dict]:
    """Fetches data from GET /drep_updates for a single DRep ID."""
    if not drep_id:
        return []
    params = {
        "_drep_id": drep_id,
        "limit": str(config.KOIOS_MAX_LIMIT),
    }  # Fetch max items
    try:
        return await _make_request("GET", "/drep_updates", params=params)
    except Exception as e:
        logger.error(f"Error fetching DRep updates for {drep_id}: {e}")
        return []


async def get_drep_delegators(drep_id: str) -> list[dict]:
    """Fetches data from GET /drep_delegators for a single DRep ID."""
    if not drep_id:
        return []
    all_delegators = []
    offset = 0
    while True:
        params = {
            "_drep_id": drep_id,
            "limit": str(config.KOIOS_MAX_LIMIT),
            "offset": str(offset),
        }
        try:
            page_results = await _make_request("GET", "/drep_delegators", params=params)
            if not page_results:  # Empty list means no more data
                break
            all_delegators.extend(page_results)
            if len(page_results) < config.KOIOS_MAX_LIMIT:  # Last page
                break
            offset += config.KOIOS_MAX_LIMIT
        except Exception as e:
            logger.error(
                f"Error fetching DRep delegators for {drep_id} at offset {offset}: {e}"
            )
            break  # Stop if there's an error on any page
    return all_delegators


async def get_proposal_list() -> list[dict]:
    """Fetches data from GET /proposal_list."""
    all_proposals = []
    offset = 0
    while True:
        params = {"limit": str(config.KOIOS_MAX_LIMIT), "offset": str(offset)}
        try:
            page_results = await _make_request("GET", "/proposal_list", params=params)
            if not page_results:  # Empty list means no more data
                break
            all_proposals.extend(page_results)
            if len(page_results) < config.KOIOS_MAX_LIMIT:  # Last page
                break
            offset += config.KOIOS_MAX_LIMIT
        except Exception as e:
            logger.error(f"Error fetching proposal list at offset {offset}: {e}")
            break  # Stop if there's an error on any page
    return all_proposals


async def get_proposal_votes(proposal_id: str) -> list[dict]:
    """Fetches data from GET /proposal_votes for a single proposal ID."""
    if not proposal_id:
        return []

    all_votes = []
    offset = 0
    # Apply MAX_PROPOSAL_VOTES_TO_FETCH if it's less than KOIOS_MAX_LIMIT or handle total limit
    # For simplicity, we'll fetch up to MAX_PROPOSAL_VOTES_TO_FETCH in chunks of KOIOS_MAX_LIMIT

    # Determine the effective limit per page and total limit for this call
    page_limit = config.KOIOS_MAX_LIMIT
    # If MAX_PROPOSAL_VOTES_TO_FETCH is set and smaller than default page limit, use it.
    # This logic might need refinement based on how MAX_PROPOSAL_VOTES_TO_FETCH is intended to be used.
    # For now, let's assume we fetch in pages of KOIOS_MAX_LIMIT until we reach MAX_PROPOSAL_VOTES_TO_FETCH or no more data.

    total_fetched = 0

    while True:
        # Determine if we need to adjust the limit for the last page to not exceed MAX_PROPOSAL_VOTES_TO_FETCH
        current_page_limit = page_limit
        if config.MAX_PROPOSAL_VOTES_TO_FETCH > 0:  # If a specific cap is set
            remaining_to_fetch = config.MAX_PROPOSAL_VOTES_TO_FETCH - total_fetched
            if remaining_to_fetch <= 0:  # Already fetched enough
                break
            current_page_limit = min(page_limit, remaining_to_fetch)

        if (
            current_page_limit <= 0
        ):  # Should not happen if logic is correct, but as a safeguard
            break

        params = {
            "_proposal_id": proposal_id,
            "limit": str(current_page_limit),
            "offset": str(offset),
        }
        try:
            page_results = await _make_request("GET", "/proposal_votes", params=params)
            if not page_results:  # Empty list means no more data for this proposal_id
                break

            all_votes.extend(page_results)
            total_fetched += len(page_results)

            if len(page_results) < current_page_limit:  # Last page for this proposal_id
                break

            if (
                config.MAX_PROPOSAL_VOTES_TO_FETCH > 0
                and total_fetched >= config.MAX_PROPOSAL_VOTES_TO_FETCH
            ):
                logger.info(
                    f"Reached MAX_PROPOSAL_VOTES_TO_FETCH ({config.MAX_PROPOSAL_VOTES_TO_FETCH}) for proposal {proposal_id}."
                )
                break

            offset += page_limit  # Increment offset by the standard page_limit for the next full page request
            await asyncio.sleep(
                config.KOIOS_API_CALL_DELAY_SECONDS
            )  # Add a small delay between pagination requests

        except Exception as e:
            logger.error(
                f"Error fetching proposal votes for {proposal_id} at offset {offset}: {e}"
            )
            break  # Stop if there's an error on any page

    return all_votes


async def get_tip() -> list[dict]:
    """Fetches data from GET /tip endpoint.
    Returns a list containing a single dictionary with tip information, or an empty list on error.
    """
    try:
        # The _make_request function is expected to return a list (even for single object results from Koios)
        # or raise an exception.
        tip_data = await _make_request("GET", "/tip")
        if tip_data and isinstance(tip_data, list) and len(tip_data) > 0:
            return tip_data
        logger.warning(f"Received unexpected or empty data from /tip: {tip_data}")
        return []
    except Exception as e:
        logger.error(f"Error fetching chain tip: {e}")
        return []


async def get_epoch_for_timestamp(timestamp: int) -> Optional[int]:
    """
    Fetches the epoch number for a given Unix timestamp by finding a block
    at or immediately after that timestamp.

    Args:
        timestamp: The Unix timestamp (seconds since epoch).

    Returns:
        The epoch number if a block is found, otherwise None.
    """
    if not isinstance(timestamp, int) or timestamp <= 0:
        logger.warning(
            f"Invalid timestamp provided to get_epoch_for_timestamp: {timestamp}"
        )
        return None

    logger.info(f"Attempting to find epoch for timestamp: {timestamp}")

    # Parameters to find the first block at or after the given timestamp
    # Koios uses 'gte.value' for 'greater than or equal to'.
    # Sorting by block_time ascending and limiting to 1 ensures we get the earliest block.
    params = {
        "_block_time": f"gte.{timestamp}",  # Greater than or equal to the timestamp
        "_order": "block_time.asc",  # Get the earliest block first
        "_limit": "1",  # We only need one block
    }

    try:
        block_data = await _make_request("GET", "/blocks", params=params)
        if block_data and isinstance(block_data, list) and len(block_data) > 0:
            block = block_data[0]
            epoch_no = block.get("epoch_no")
            block_time_retrieved = block.get(
                "block_time"
            )  # Unix timestamp of the block

            if epoch_no is not None:
                logger.info(
                    f"Found epoch {epoch_no} for timestamp {timestamp} (block time: {block_time_retrieved})"
                )
                return int(epoch_no)
            else:
                logger.warning(
                    f"No 'epoch_no' found in block data for timestamp {timestamp}. Block data: {block}"
                )
                return None
        else:
            await _make_request(
                "GET",
                "/blocks",
                params={
                    "_block_time": f"lt.{timestamp}",
                    "_order": "block_time.desc",
                    "_limit": "1",
                },
            )
            # Fallback for weird edge cases if needed, but the original logic is usually sound for 'epoch at timestamp'.
            # Ideally epoch at timestamp T is the epoch of the block B where B.time <= T < B_next.time
            # But here we look for block >= T. If T is in epoch N, the next block >= T will be in epoch N (or N+1 if T was during the boundary gap).
            # The original logic is likely acceptable for this MVP level.

            logger.info(f"No block found at or after timestamp {timestamp}.")
            return None
    except Exception as e:
        # _make_request already logs details of HTTP errors.
        logger.error(f"Error fetching block for timestamp {timestamp}: {e}")
        return None


if __name__ == "__main__":
    # Basic test calls (ensure your config.py is set up)
    # This section will only run if you execute this file directly.
    # It's good for quick, isolated testing of the API functions.

    logging.basicConfig(level=logging.INFO)  # Ensure we see logs

    async def run_tests():
        logger.info("--- Testing Koios API Functions ---")

        # Test get_drep_info
        if config.INITIAL_DREP_LIST:
            test_drep_id_info = config.INITIAL_DREP_LIST[0]
            logger.info(f"\nTesting get_drep_info with DRep ID: {test_drep_id_info}")
            try:
                drep_info_data = await get_drep_info([test_drep_id_info])
                if drep_info_data:
                    logger.info(
                        f"DRep Info for {test_drep_id_info}: {drep_info_data[0]}"
                    )
                else:
                    logger.warning(f"No DRep info returned for {test_drep_id_info}")
            except Exception as e:
                logger.error(f"get_drep_info test failed: {e}")

            # Test get_drep_updates
            logger.info(f"\nTesting get_drep_updates with DRep ID: {test_drep_id_info}")
            try:
                drep_updates_data = await get_drep_updates(test_drep_id_info)
                if drep_updates_data:
                    logger.info(
                        f"DRep Updates for {test_drep_id_info} (first update): {drep_updates_data[0]}"
                    )
                else:
                    logger.warning(f"No DRep updates returned for {test_drep_id_info}")
            except Exception as e:
                logger.error(f"get_drep_updates test failed: {e}")

            # Test get_drep_delegators
            logger.info(
                f"\nTesting get_drep_delegators with DRep ID: {test_drep_id_info}"
            )
            try:
                drep_delegators_data = await get_drep_delegators(test_drep_id_info)
                logger.info(
                    f"Found {len(drep_delegators_data)} delegators for {test_drep_id_info}."
                )
                if drep_delegators_data:
                    logger.info(
                        f"First delegator for {test_drep_id_info}: {drep_delegators_data[0]}"
                    )
            except Exception as e:
                logger.error(f"get_drep_delegators test failed: {e}")
        else:
            logger.warning(
                "INITIAL_DREP_LIST is empty in config.py, skipping DRep specific tests."
            )

        # Test get_proposal_list
        logger.info("\nTesting get_proposal_list (fetching first few)...")
        try:
            proposal_list_data = (
                await get_proposal_list()
            )  # This will fetch all, could be large.
            if proposal_list_data:
                logger.info(f"Total proposals fetched: {len(proposal_list_data)}")
                test_proposal = proposal_list_data[0]
                logger.info(f"First proposal: {test_proposal}")

                # Test get_proposal_votes with the first proposal's ID
                proposal_id_to_test = test_proposal.get("proposal_id")
                if proposal_id_to_test:
                    logger.info(
                        f"\nTesting get_proposal_votes with Proposal ID: {proposal_id_to_test}"
                    )
                    try:
                        proposal_votes_data = await get_proposal_votes(
                            proposal_id_to_test
                        )
                        logger.info(
                            f"Found {len(proposal_votes_data)} votes for proposal {proposal_id_to_test}."
                        )
                        if proposal_votes_data:
                            logger.info(
                                f"First vote for proposal {proposal_id_to_test}: {proposal_votes_data[0]}"
                            )
                    except Exception as e:
                        logger.error(f"get_proposal_votes test failed: {e}")
                else:
                    logger.warning(
                        "Could not get proposal_id from the first proposal to test get_proposal_votes."
                    )
            else:
                logger.warning("No proposals returned by get_proposal_list.")
        except Exception as e:
            logger.error(f"get_proposal_list test failed: {e}")

        logger.info("\nTesting get_epoch_for_timestamp...")
        # Example: Timestamp for sometime on May 20, 2024.
        test_timestamp = 1716192000
        try:
            epoch_for_timestamp = await get_epoch_for_timestamp(test_timestamp)
            if epoch_for_timestamp is not None:
                logger.info(
                    f"Epoch for timestamp {test_timestamp}: {epoch_for_timestamp} (Test considered successful if an epoch is returned)"
                )
            else:
                logger.warning(
                    f"No epoch returned for timestamp {test_timestamp}. This might be okay if no block exists at this exact second, or an API/logic issue."
                )
        except Exception as e:
            logger.error(
                f"get_epoch_for_timestamp test call failed: {e}", exc_info=True
            )

        logger.info("\n--- Koios API Function Tests Complete ---")

    asyncio.run(run_tests())
