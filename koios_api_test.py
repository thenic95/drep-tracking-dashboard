import httpx
import json

# API Configuration
BASE_URL = "https://api.koios.rest/api/v1"
import os
from dotenv import load_dotenv

# Load from backend/.env
load_dotenv("backend/.env")
API_TOKEN = os.getenv("KOIOS_API_TOKEN")
HEADERS_POST = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}
HEADERS_GET = {"Authorization": f"Bearer {API_TOKEN}"}

# Target DRep ID
DREP_ID_TEST = "drep1y2eu92qwy875nlslg3ahlh0hy5vhzpkrjay88ptvdp0z6cqm9h25x"

def print_response_summary(response):
    """Prints a summary of the JSON response."""
    try:
        json_response = response.json()
        if isinstance(json_response, list):
            print(f"Response JSON (count: {len(json_response)}):")
            if len(json_response) > 0:
                print(json.dumps(json_response[0], indent=2)) # Print first element
                if len(json_response) > 1:
                    print(f"... and {len(json_response) - 1} more element(s).")
            else:
                print("[]") # Empty list
        elif isinstance(json_response, dict):
            summary = {k: json_response[k] for i, k in enumerate(json_response) if i < 5 }
            print(f"Response JSON (summary): {json.dumps(summary, indent=2)}")
        else:
            print(f"Response JSON: {json.dumps(json_response, indent=2)}")
    except json.JSONDecodeError:
        print(f"Response content (not JSON or empty): {response.text[:200]}...")
    except Exception as e:
        print(f"Error printing response summary: {e}")

def test_drep_info():
    """Tests the /drep_info endpoint (POST)."""
    endpoint = "/drep_info"
    url = BASE_URL + endpoint
    payload = {"_drep_ids": [DREP_ID_TEST]}
    print(f"\nQuerying endpoint: POST {endpoint}")
    print(f"Payload: {payload}")
    try:
        response = httpx.post(url, headers=HEADERS_POST, json=payload)
        print(f"Status Code: {response.status_code}")
        print_response_summary(response)
        if response.status_code == 200 and response.json():
            # Extract voting power for summary
            data = response.json()
            if data and isinstance(data, list) and data[0].get("amount"):
                return {"success": True, "voting_power": data[0]["amount"]}
            return {"success": True, "voting_power": "N/A"}
        return {"success": False}
    except httpx.RequestError as e:
        print(f"Error: {e}")
        return {"success": False}

def test_drep_updates():
    """Tests the /drep_updates endpoint (GET)."""
    endpoint = "/drep_updates"
    url = BASE_URL + endpoint
    params = {"_drep_id": DREP_ID_TEST}
    print(f"\nQuerying endpoint: GET {endpoint}")
    print(f"Params: {params}")
    try:
        response = httpx.get(url, headers=HEADERS_GET, params=params)
        print(f"Status Code: {response.status_code}")
        print_response_summary(response)
        return response.status_code == 200
    except httpx.RequestError as e:
        print(f"Error: {e}")
        return False

def test_drep_delegators():
    """Tests the /drep_delegators endpoint (GET) for delegator count."""
    endpoint = "/drep_delegators"
    url = BASE_URL + endpoint
    params = {"_drep_id": DREP_ID_TEST}
    print(f"\nQuerying endpoint: GET {endpoint}")
    print(f"Params: {params}")
    try:
        response = httpx.get(url, headers=HEADERS_GET, params=params)
        print(f"Status Code: {response.status_code}")
        print_response_summary(response)
        if response.status_code == 200 and isinstance(response.json(), list):
            return {"success": True, "delegator_count": len(response.json())}
        return {"success": False}
    except httpx.RequestError as e:
        print(f"Error: {e}")
        return {"success": False}

def test_proposal_list():
    """Tests the /proposal_list endpoint (GET)."""
    endpoint = "/proposal_list"
    url = BASE_URL + endpoint
    print(f"\nQuerying endpoint: GET {endpoint}")
    try:
        response = httpx.get(url, headers=HEADERS_GET, params={"limit": "5"}) # Limit for brevity
        print(f"Status Code: {response.status_code}")
        print_response_summary(response)
        if response.status_code == 200 and response.json():
            proposals = response.json()
            if proposals:
                # Construct proposal_id from tx_hash and proposal_index for the next test
                # The API spec defines _proposal_id as "Government proposal ID in CIP-129 Bech32 format"
                # or implies tx_hash_certindex. Let's find one with 'proposal_id' field if available, else construct.
                for p in proposals:
                    if p.get("proposal_id"): # This is the bech32 CIP-129 id
                        return {"success": True, "proposal_id_to_test": p["proposal_id"]}
                # Fallback: if no direct proposal_id (bech32) is found, try constructing from older fields
                # This might be needed if the API returns older formats sometimes or if CIP-129 IDs are not on all proposals
                first_proposal = proposals[0]
                if first_proposal.get("proposal_tx_hash") is not None and first_proposal.get("proposal_index") is not None:
                     constructed_id = f"{first_proposal['proposal_tx_hash']}_{first_proposal['proposal_index']}"
                     print(f"Using constructed proposal_id for next test: {constructed_id}")
                     return {"success": True, "proposal_id_to_test": constructed_id}
            print("No proposals found or proposal_id field missing in first proposal.")
            return {"success": True, "proposal_id_to_test": None} # Success but no ID to test
        return {"success": False}
    except httpx.RequestError as e:
        print(f"Error: {e}")
        return {"success": False}

def test_proposal_votes(proposal_id_to_test):
    """Tests the /proposal_votes endpoint (GET)."""
    if not proposal_id_to_test:
        print("\nSkipping /proposal_votes test as no proposal_id was retrieved.")
        return False
    
    endpoint = "/proposal_votes"
    url = BASE_URL + endpoint
    # The parameter name according to koiosapi.yaml is _proposal_id
    # Removed 'eq.' prefix as per investigation of the 404 error.
    params = {"_proposal_id": proposal_id_to_test} 
    print(f"\nQuerying endpoint: GET {endpoint}")
    print(f"Params: {params}")
    try:
        response = httpx.get(url, headers=HEADERS_GET, params=params)
        print(f"Status Code: {response.status_code}")
        print_response_summary(response)
        # It's possible a proposal has no votes yet, so 200 and empty list is success
        return response.status_code == 200
    except httpx.RequestError as e:
        try:
           # Try to print response text if available in exception for debugging, 
           # though RequestError might not have it. HTTPStatusError would.
           pass
        except:
            pass
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Starting Koios API Endpoint Verification with Corrected Paths...")
    
    final_summary_lines = []
    overall_success = True

    # 1. DRep Info & Voting Power
    drep_info_result = test_drep_info()
    if drep_info_result.get("success"):
        final_summary_lines.append(f"- /drep_info (DRep Registration Info): SUCCESS (Voting Power: {drep_info_result.get('voting_power', 'N/A')})")
    else:
        final_summary_lines.append("- /drep_info (DRep Registration Info): FAILURE")
        overall_success = False

    # 2. DRep Activity/History
    drep_updates_status = test_drep_updates()
    if drep_updates_status:
        final_summary_lines.append("- /drep_updates (DRep Activity/History): SUCCESS")
    else:
        final_summary_lines.append("- /drep_updates (DRep Activity/History): FAILURE")
        overall_success = False

    # 3. DRep Delegators Count
    drep_delegators_result = test_drep_delegators()
    if drep_delegators_result.get("success"):
        final_summary_lines.append(f"- /drep_delegators (DRep Delegator Count): SUCCESS (Count: {drep_delegators_result.get('delegator_count', 'N/A')})")
    else:
        final_summary_lines.append("- /drep_delegators (DRep Delegator Count): FAILURE")
        overall_success = False
        
    # 4. Governance Actions List
    proposal_list_result = test_proposal_list()
    proposal_id_for_next_test = None
    if proposal_list_result.get("success"):
        final_summary_lines.append("- /proposal_list (Governance Actions List): SUCCESS")
        proposal_id_for_next_test = proposal_list_result.get("proposal_id_to_test")
        if not proposal_id_for_next_test:
            final_summary_lines.append("  - Note: No proposal_id found in /proposal_list response to test /proposal_votes.")
    else:
        final_summary_lines.append("- /proposal_list (Governance Actions List): FAILURE")
        overall_success = False

    # 5. DRep Votes for a specific GA
    if proposal_id_for_next_test:
        proposal_votes_status = test_proposal_votes(proposal_id_for_next_test)
        if proposal_votes_status:
            final_summary_lines.append(f"- /proposal_votes (Votes for GA ID {proposal_id_for_next_test}): SUCCESS")
        else:
            final_summary_lines.append(f"- /proposal_votes (Votes for GA ID {proposal_id_for_next_test}): FAILURE")
            overall_success = False
    else:
        final_summary_lines.append("- /proposal_votes: SKIPPED (no proposal_id from /proposal_list)")
        # Not necessarily a failure of overall_success if /proposal_list was empty but successful.
        # However, if /proposal_list failed, overall_success is already false.

    print("\n--- Koios API Verification Summary ---")
    for line in final_summary_lines:
        print(line)

    if overall_success:
        print("\nSUCCESS: API token is functional and all key corrected DRep-related endpoints provided the expected data structure or response.")
    else:
        print("\nFAILURE: Some issues encountered with corrected endpoints. Please review the logs above.")
        print("Ensure the API token is valid and has not expired. Also, check individual endpoint responses for specific errors.")

    # For submission
    # submit_summary = "\n".join(final_summary_lines)
    # submit_summary += f"\n\nOverall Result: {'SUCCESS' if overall_success else 'FAILURE'}"
    # print(f"\nFOR SUBMISSION:\n{submit_summary}")
    # This will be handled by the agent in the next step.
