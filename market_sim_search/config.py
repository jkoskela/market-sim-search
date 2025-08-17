import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

import pytz

EST = pytz.timezone('US/Eastern')

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"


def is_ipython():
    hasattr(__builtins__, '__IPYTHON__')


# Configure logging
logger.remove(None)
fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{function}: {message}</level>"
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_path = Path(os.getenv("LOG_PATH", f"{PROJ_ROOT}/app.log"))
log_path.parent.mkdir(parents=True, exist_ok=True)

logger.add(
    log_path,
    level=log_level,
    rotation="1 day",
    retention="3 days"
)


# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass
