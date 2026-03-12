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

# CF (Cardano Foundation) stake addresses for delegation tracking.
# Add CF stake credentials/addresses here to enable CF delegation monitoring.
CF_STAKE_ADDRESSES: list[str] = [
    "stake1u99w898wvj7qep8zx3gex33zx0rsknefdfwj6mmnwzw48dslk64yh",
    "stake1u8m40a3e59jp452zdz07mjzmu90eqvff9xj9ydqx7fxla2q87uq34",
    "stake1uynh8xncj7kw4a9taaykxy75mjkjw3pgpvyzyt9pwyslktcxm5xd5",
    "stake1uxd9q7efgpr52cq5d7pda9dajftglx0s2s3532uapvum5dc3mcrs2",
    "stake1uyv8t8l39dmyznv8cqgmqklmtnkvxktd2c4l26al6j85y7q8wk0ra",
    "stake1u8uee2s3y3svc8237nm0mpcsd0qw2pvzu0hn8kal32jrlxg04r3wf",
    "stake1u9u2zwvxp79j7gg38mqlv2km52h77rsqxun5f6lr4m2j7dsraacmr",
    "stake1u9al6v4vdukkaukt8zl7jq3z7jmarlsfel6rse6n5khg96srwa5ac",
    "stake1uxwcg93y4kjumxupyzpechxx2239ctzyg35xga84tgtrqwgxmgsn9",
    "stake1uxdmpfm2s06k097lmsv8wc00gz073crwhrpa6a3dv2p2gqcqla5lq",
    "stake1u9uq8gqap39g4pepvpqq7497dlwsk3ka7kc4x6rgdguxs5su6h9ms",
    "stake1ux6x6qpuugradesquz4s022cdj7r3cu2pjsxnxv37fe20sqy89l4w",
    "stake1u8x2luu4ke99tx4rnhwhm69zmkkrpsmylgcr7f4xad8hsqgssp4mt",
    "stake1uypx7jdzh4yqw04axshzgk5lwxkq8wd0r6wx4rz2zs6377smlshv7",
    "stake1uxv8rj3l09ks9ha7zf55e65sduqelak5sgpt56va8l4zz2cv3mqqr",
    "stake1uxz9szw7xl7rnaxn66x8r8cfnetfg0mx60z4pfd70vwk65gw6madt",
    "stake1u99rxmppp5kmurxzzmzwvydupwh6c590w57m403y292a06qxwuyra",
    "stake1uyx6hgdkqvg0tps20z7mh2utvngvharv39p5elyrglkth6gltznm3",
]

# Define the path for the database file relative to the backend directory
# BACKEND_DIR is already defined at the top
DB_PATH = os.path.join(BACKEND_DIR, DB_FILE)
