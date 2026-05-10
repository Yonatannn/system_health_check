from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET


def is_valid_xml(path: Path) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    try:
        ET.parse(str(path))
        return True, ""
    except ET.ParseError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
