import os
from pathlib import Path

ABS_PATH = os.getcwd()
HOME_DIR = str(Path.home())
CONFIG_DIR = os.path.join(HOME_DIR, ".embedchain")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SQLITE_PATH = os.path.join(CONFIG_DIR, "embedchain.db")
