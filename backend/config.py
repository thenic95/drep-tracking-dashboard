import os

from dotenv import load_dotenv

# Determine the directory of this file
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
# Load environment variables from .env file in the same directory
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

KOIOS_API_TOKEN = os.getenv("KOIOS_API_TOKEN")

INITIAL_DREP_LIST = [
    "drep1y2eu92qwy875nlslg3ahlh0hy5vhzpkrjay88ptvdp0z6cqm9h25x",
    "drep1yglrf4el8gghum239fggvfrau25k2576y4dvcz65r2ukj8sqpsc2k",
    "drep1yfjez5zup0gystdvc933w2mn8k64hcy3krvc2namluwjxdcfhm8wd",
    "drep1ytcv4ax77s0enqef56qjflf4d8zjgxulukme9uf5p8cfaagysjppn",
    "drep1ytzshxuma6cwrnlv2ucyclfqw3k4nu4nuudmh2z87j9hncsk9dhy4",
    "drep1yfa8r8r36x7x05htftce7qhafrn5nzzr6vazy95pzy6y5dqac0ss7",
    "drep1yv4uesaj92wk8ljlsh4p7jzndnzrflchaz5fzug3zxg4naqkpeas3",
]

KOIOS_API_BASE_URL = "https://api.koios.rest/api/v1"
DB_FILE = "drep_tracker.db"  # Will be backend/drep_tracker.db
LOG_LEVEL = "INFO"  # For logging configuration
REQUESTS_TIMEOUT = 30  # seconds
MAX_KOIOS_BULK_ITEMS = 100  # Koios has a limit for bulk requests, typically 1000, but smaller batches can be safer. Check Koios docs for exact limits.
# For /drep_info, the underlying function in GRest has a limit of 1000 _drep_ids.
# For other bulk endpoints, it might vary. Let's assume 100 for safety if not specified.
KOIOS_MAX_LIMIT = 1000  # Default max items per page from Koios
MAX_PROPOSAL_VOTES_TO_FETCH = (
    500  # Limit number of votes fetched per proposal for now to avoid very long calls.
)
# Set to 0 to fetch votes for all proposals. Previously limited to the last
# few proposals which meant older governance actions had no vote data.
MAX_PROPOSALS_TO_PROCESS_INITIALLY = 0
GA_RECENCY_EPOCH_WINDOW = 2  # Number of previous epochs (plus current) to consider for re-fetching votes for GAs.

# Retry mechanism parameters for Koios API calls
KOIOS_RETRY_ATTEMPTS = 3  # Number of retry attempts
KOIOS_RETRY_DELAY = 1  # Initial delay in seconds
KOIOS_RETRY_BACKOFF_FACTOR = 2  # Factor by which the delay increases (e.g., 1s, 2s, 4s)
KOIOS_API_CALL_DELAY_SECONDS = (
    0.2  # Delay between individual Koios API calls within loops to respect rate limits
)

# Define the path for the database file relative to the backend directory
# BACKEND_DIR is already defined at the top
DB_PATH = os.path.join(BACKEND_DIR, DB_FILE)
