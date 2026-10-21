import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def watchlist() -> dict:
    path = Path(os.getenv("LISTENER_WATCHLIST", ROOT / "config" / "watchlist.yaml"))
    cfg = yaml.safe_load(path.read_text())
    cfg["competitors"] = {k: [a.lower() for a in v] for k, v in cfg["competitors"].items()}
    return cfg
