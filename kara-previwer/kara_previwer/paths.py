"""User directories shared by vibekara's installer and review tools."""

import os
from pathlib import Path


def vibekara_home() -> Path:
    return Path(os.environ.get("VIBEKARA_HOME") or Path.home() / ".vibekara").expanduser().resolve()
