import logging
from datetime import date, datetime
from typing import Any

from google.auth import default as application_default
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import service_account_info, spreadsheet_id
from .models import Priority, Task, TaskStatus, calculate_task_state

logger = logging.getLogger(__name__)

HEADERS = [
    "task_id",
    "title",
    "description",
    "task_date",
    "priority",
    "status",
    "created_at",
    "updated_at",
    "completed_at",
    "deleted",
]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class StorageError(RuntimeError):
    pass


class TaskNotFoundError(LookupError):
    pass


class SheetsStore:
    def __init__(self) -> None:
        self._spreadsheet_id = spreadsheet_id()
        info = service_account_info()
        if info:
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )
        else:
            credentials, _ = application_default(scopes=SCOPES)
        self._sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def _call(self, request: Any) -> Any:
        try:
            return request.execute()
        except HttpError as exc:
            status = exc.resp.status
            logger.error("Google Sheets API request failed with HTTP %s.", status)
            if status in (401, 403):
                message = (
                    "Google Sheets denied access. Check that the Sheets API is enabled "
                    "and that the spreadsheet is shared with the service-account email "
                    "as an Editor."
                )
            elif status == 404:
                message = (
                    "Google Sheets could not find or access the spreadsheet. Check that "
                    "GOOGLE_SHEETS_SPREADSHEET_ID is correct and that the spreadsheet is "
                    "shared with the service-account email as an Editor."
                )
            else:
                message = (
                    f"Google Sheets returned HTTP {status}. Check the spreadsheet ID, "
                    "the Tasks worksheet, and the backend log for details."
                )
            raise StorageError(message) from exc
        except Exception as exc:
            logger.exception("Could not access Google Sheets.")
            raise StorageError("Could not access Google Sheets. Check server configuration.") from exc

    def _ensure_task_sheet(self) -> None:
        result = self._call(
            self._sheets.spreadsheets().get(
                spreadsheetId=self._spreadsheet_id,
                fields="sheets.properties(sheetId,title)",
            )
        )
        sheet_exists = any(
            sheet.get("properties", {}).get("title") == "Tasks"
            for sheet in result.get("sheets", [])
        )
        if not sheet_exists:
            self._call(
                self._sheets.spreadsheets().batchUpdate(
                    spreadsheetId=self._spreadsheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": "Tasks"}}}]},
                )
            )

    def _ensure_headers(self) -> None:
        self._ensure_task_sheet()
        result = self._call(
            self._sheets.spreadsheets().values().get(
                spreadsheetId=self._spreadsheet_id, range="Tasks!A1:J1"
            )
        )
        values = result.get("values", [])
        if values and values[0] == HEADERS:
            return
        if values and values[0]:
            raise StorageError("The Tasks sheet has unexpected columns; expected task headers.")
        self._call(
            self._sheets.spreadsheets().values().update(
                spreadsheetId=self._spreadsheet_id,
                range="Tasks!A1:J1",
                valueInputOption="RAW",
                body={"values": [HEADERS]},
            )
        )

    def _rows(self) -> list[list[str]]:
        self._ensure_headers()
        result = self._call(
            self._sheets.spreadsheets().values().get(
                spreadsheetId=self._spreadsheet_id, range="Tasks!A2:J"
            )
        )
        return result.get("values", [])

    @staticmethod
    def _task(row: list[str]) -> dict[str, str]:
        padded = row + [""] * (len(HEADERS) - len(row))
        return dict(zip(HEADERS, padded))

    def list_tasks(self, include_deleted: bool = False) -> list[dict[str, Any]]:
        items = [self._task(row) for row in self._rows()]
        return items if include_deleted else [item for item in items if item["deleted"].lower() != "true"]

    def add_task(self, task: Task) -> None:
        self._ensure_headers()
        values = [[
            task.task_id,
            task.title,
            task.description,
            task.task_date.isoformat(),
            task.priority.value,
            task.status.value,
            task.created_at.isoformat(),
            task.updated_at.isoformat(),
            task.completed_at.isoformat() if task.completed_at else "",
            "FALSE",
        ]]
        self._call(
            self._sheets.spreadsheets().values().append(
                spreadsheetId=self._spreadsheet_id,
                range="Tasks!A:J",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            )
        )

    def update_task(self, task_id: str, task: Task) -> None:
        rows = self._rows()
        for index, row in enumerate(rows, start=2):
            existing = self._task(row)
            if existing["task_id"] == task_id and existing["deleted"].lower() != "true":
                values = [[
                    task.task_id,
                    task.title,
                    task.description,
                    task.task_date.isoformat(),
                    task.priority.value,
                    task.status.value,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else "",
                    "FALSE",
                ]]
                self._call(
                    self._sheets.spreadsheets().values().update(
                        spreadsheetId=self._spreadsheet_id,
                        range=f"Tasks!A{index}:J{index}",
                        valueInputOption="RAW",
                        body={"values": values},
                    )
                )
                return
        raise TaskNotFoundError(task_id)

    def set_status(self, task_id: str, status: TaskStatus, updated_at: datetime) -> None:
        rows = self._rows()
        for index, row in enumerate(rows, start=2):
            existing = self._task(row)
            if existing["task_id"] == task_id and existing["deleted"].lower() != "true":
                completed_at = updated_at.isoformat() if status == TaskStatus.COMPLETED else ""
                self._call(
                    self._sheets.spreadsheets().values().update(
                        spreadsheetId=self._spreadsheet_id,
                        range=f"Tasks!F{index}:I{index}",
                        valueInputOption="RAW",
                        body={
                            "values": [[
                                status.value,
                                existing["created_at"],
                                updated_at.isoformat(),
                                completed_at,
                            ]]
                        },
                    )
                )
                return
        raise TaskNotFoundError(task_id)

    def delete_task(self, task_id: str, updated_at: datetime) -> None:
        rows = self._rows()
        for index, row in enumerate(rows, start=2):
            existing = self._task(row)
            if existing["task_id"] == task_id and existing["deleted"].lower() != "true":
                self._call(
                    self._sheets.spreadsheets().values().update(
                        spreadsheetId=self._spreadsheet_id,
                        range=f"Tasks!H{index}:J{index}",
                        valueInputOption="RAW",
                        body={"values": [[updated_at.isoformat(), "", "TRUE"]]},
                    )
                )
                return
        raise TaskNotFoundError(task_id)


def parse_task(row: dict[str, str], today: date) -> Task:
    try:
        task_date = date.fromisoformat(row["task_date"])
        status = TaskStatus(row["status"])
        completed_at = datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        state = calculate_task_state(status, task_date, today)
        return Task(
            task_id=row["task_id"],
            title=row["title"],
            description=row["description"],
            task_date=task_date,
            priority=Priority(row["priority"]),
            status=status,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=completed_at,
            deleted=row["deleted"].lower() == "true",
            state=state,
        )
    except (KeyError, ValueError) as exc:
        raise StorageError(f"Invalid task record in Google Sheets: {exc}") from exc
