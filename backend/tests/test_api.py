import os
import sys

from fastapi.testclient import TestClient

# Adjust path to import app from backend.main
# This assumes tests might be run from the root directory or 'backend/tests'
# For robust path handling, consider project structure and how tests are invoked.
# A common pattern is to add the project root to sys.path if needed.
try:
    from backend.main import app
except ImportError:
    # This is a simplified way to handle path for the subtask.
    # A more robust solution might involve PYTHONPATH or project structure conventions.
    # Assuming 'backend' is a sibling to the directory where the command is run from, or is the current dir.
    # Or if tests are run from root:
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    )
    from backend.main import app


client = TestClient(app)


def test_get_governance_actions():
    response = client.get("/api/governance-actions")
    assert response.status_code == 200
    # Optional: Check if the response is a list (JSON array)
    assert isinstance(response.json(), list)


def test_get_tracked_dreps():
    response = client.get("/api/dreps/tracked")
    assert response.status_code == 200
    # Optional: Check if the response is a list (JSON array)
    assert isinstance(response.json(), list)


# To make these runnable directly for verification (optional):
if __name__ == "__main__":
    print("Running API tests...")
    test_get_governance_actions()
    print("test_get_governance_actions: PASSED (if no assertion error)")
    test_get_tracked_dreps()
    print("test_get_tracked_dreps: PASSED (if no assertion error)")
    print("All basic API tests seem to pass.")
