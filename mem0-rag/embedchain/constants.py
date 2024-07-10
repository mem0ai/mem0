import os
from pathlib import Path

ABS_PATH = os.getcwd()
HOME_DIR = os.environ.get("EMBEDCHAIN_CONFIG_DIR", str(Path.home()))
CONFIG_DIR = os.path.join(HOME_DIR, ".embedchain")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SQLITE_PATH = os.path.join(CONFIG_DIR, "embedchain.db")

# Set the environment variable for the database URI
os.environ.setdefault("EMBEDCHAIN_DB_URI", f"sqlite:///{SQLITE_PATH}")
