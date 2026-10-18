import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SettingsError(ValueError):
    pass


@lru_cache
def timezone() -> ZoneInfo:
    name = os.getenv("APP_TIMEZONE", "UTC")
    if name.upper() == "IST":
        name = "Asia/Kolkata"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise SettingsError(f"Unknown APP_TIMEZONE: {name}") from exc


def spreadsheet_id() -> str:
    value = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    if not value:
        raise SettingsError("GOOGLE_SHEETS_SPREADSHEET_ID is not configured.")
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return value
    raise SettingsError(
        "GOOGLE_SHEETS_SPREADSHEET_ID must be a spreadsheet ID or a Google Sheets URL."
    )


def service_account_info() -> dict[str, Any] | None:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw and raw.strip():
        value = raw.strip()
        try:
            info = json.loads(value)
        except json.JSONDecodeError as exc:
            credential_path = Path(os.path.expandvars(value)).expanduser()
            if credential_path.is_file():
                try:
                    info = json.loads(credential_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as file_exc:
                    raise SettingsError(
                        "GOOGLE_SERVICE_ACCOUNT_JSON points to a file that could not be "
                        "read as valid service-account JSON."
                    ) from file_exc
            else:
                raise SettingsError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON must contain the full service-account JSON "
                    "or a path to its JSON key file. Alternatively, leave it blank and set "
                    "GOOGLE_APPLICATION_CREDENTIALS to the file path."
                ) from exc
        if not isinstance(info, dict):
            raise SettingsError(
                "GOOGLE_SERVICE_ACCOUNT_JSON must contain a JSON object."
            )
        return info
    return None
