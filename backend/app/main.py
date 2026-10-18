import hmac
import logging
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import SettingsError, timezone
from .models import (
    DashboardSummary,
    Task,
    TaskInput,
    TaskStatus,
    TaskUpdate,
    calculate_task_state,
)
from .sheets_store import SheetsStore, StorageError, TaskNotFoundError, parse_task

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Personal Task Management API", version="1.0.0")
bearer_auth = HTTPBearer(auto_error=False)

origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def authorize(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_auth)],
) -> None:
    configured_token = os.getenv("API_ACCESS_TOKEN", "")
    supplied_token = credentials.credentials if credentials else ""
    if configured_token and not hmac.compare_digest(supplied_token, configured_token):
        raise HTTPException(status_code=401, detail="A valid API access token is required.")


def store() -> SheetsStore:
    try:
        return SheetsStore()
    except SettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not initialize Google Sheets storage.")
        raise HTTPException(status_code=503, detail="Google Sheets storage is not available.") from exc


def today() -> date:
    try:
        return datetime.now(timezone()).date()
    except SettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def now() -> datetime:
    return datetime.now(timezone())


def map_storage_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TaskNotFoundError):
        return HTTPException(status_code=404, detail="Task not found.")
    if isinstance(exc, StorageError):
        return HTTPException(status_code=503, detail=str(exc))
    logger.exception("Unexpected task storage error.")
    return HTTPException(status_code=500, detail="An unexpected storage error occurred.")


def load_tasks(storage: SheetsStore) -> list[Task]:
    try:
        return [parse_task(row, today()) for row in storage.list_tasks()]
    except (StorageError, TaskNotFoundError) as exc:
        raise map_storage_error(exc) from exc


@app.exception_handler(SettingsError)
async def settings_error_handler(_request, exc: SettingsError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Personal Task Management API",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": "http://localhost:5173",
    }


@app.get("/api/auth/check", dependencies=[Depends(authorize)])
def check_authentication() -> dict[str, bool]:
    return {"authenticated": True}


@app.get("/api/tasks", response_model=list[Task], dependencies=[Depends(authorize)])
def get_tasks(
    storage: Annotated[SheetsStore, Depends(store)],
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    status: TaskStatus | None = None,
) -> list[Task]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="startDate must be on or before endDate.")
    tasks = load_tasks(storage)
    if start_date:
        tasks = [task for task in tasks if task.task_date >= start_date]
    if end_date:
        tasks = [task for task in tasks if task.task_date <= end_date]
    if status:
        tasks = [task for task in tasks if task.status == status]
    return sorted(tasks, key=lambda task: (task.task_date, task.created_at))


@app.get("/api/tasks/{task_id}", response_model=Task, dependencies=[Depends(authorize)])
def get_task(task_id: str, storage: Annotated[SheetsStore, Depends(store)]) -> Task:
    for task in load_tasks(storage):
        if task.task_id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found.")


@app.post(
    "/api/tasks",
    response_model=Task,
    status_code=201,
    dependencies=[Depends(authorize)],
)
def create_task(payload: TaskInput, storage: Annotated[SheetsStore, Depends(store)]) -> Task:
    if payload.task_date < today():
        raise HTTPException(status_code=400, detail="Tasks cannot be scheduled in the past.")
    timestamp = now()
    task = Task(
        task_id=str(uuid.uuid4()),
        title=payload.title,
        description=payload.description,
        task_date=payload.task_date,
        priority=payload.priority,
        status=TaskStatus.PENDING,
        created_at=timestamp,
        updated_at=timestamp,
        state=calculate_task_state(TaskStatus.PENDING, payload.task_date, today()),
    )
    try:
        storage.add_task(task)
    except (StorageError, TaskNotFoundError) as exc:
        raise map_storage_error(exc) from exc
    return task


@app.put("/api/tasks/{task_id}", response_model=Task, dependencies=[Depends(authorize)])
def update_task(
    task_id: str,
    payload: TaskUpdate,
    storage: Annotated[SheetsStore, Depends(store)],
) -> Task:
    try:
        existing = next(
            (task for task in load_tasks(storage) if task.task_id == task_id), None
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        if payload.task_date < today() and payload.task_date != existing.task_date:
            raise HTTPException(
                status_code=400,
                detail="An existing overdue task can be kept or rescheduled to today or later.",
            )
        timestamp = now()
        updated = existing.model_copy(
            update={
                "title": payload.title,
                "description": payload.description,
                "task_date": payload.task_date,
                "priority": payload.priority,
                "updated_at": timestamp,
                "state": calculate_task_state(
                    existing.status, payload.task_date, today()
                ),
            }
        )
        storage.update_task(task_id, updated)
        return updated
    except (StorageError, TaskNotFoundError) as exc:
        raise map_storage_error(exc) from exc


@app.patch(
    "/api/tasks/{task_id}/status",
    response_model=Task,
    dependencies=[Depends(authorize)],
)
def update_status(
    task_id: str,
    status: TaskStatus,
    storage: Annotated[SheetsStore, Depends(store)],
) -> Task:
    try:
        existing = next(
            (task for task in load_tasks(storage) if task.task_id == task_id), None
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        timestamp = now()
        storage.set_status(task_id, status, timestamp)
        completed_at = timestamp if status == TaskStatus.COMPLETED else None
        state = calculate_task_state(status, existing.task_date, today())
        return existing.model_copy(
            update={
                "status": status,
                "updated_at": timestamp,
                "completed_at": completed_at,
                "state": state,
            }
        )
    except (StorageError, TaskNotFoundError) as exc:
        raise map_storage_error(exc) from exc


@app.delete("/api/tasks/{task_id}", status_code=204, dependencies=[Depends(authorize)])
def delete_task(task_id: str, storage: Annotated[SheetsStore, Depends(store)]) -> Response:
    try:
        storage.delete_task(task_id, now())
    except (StorageError, TaskNotFoundError) as exc:
        raise map_storage_error(exc) from exc
    return Response(status_code=204)


@app.get(
    "/api/reports/tasks",
    response_model=list[Task],
    dependencies=[Depends(authorize)],
)
def report_tasks(
    storage: Annotated[SheetsStore, Depends(store)],
    start_date: date = Query(alias="startDate"),
    end_date: date = Query(alias="endDate"),
    status: TaskStatus | None = None,
    completed_start_date: date | None = Query(default=None, alias="completedStartDate"),
    completed_end_date: date | None = Query(default=None, alias="completedEndDate"),
) -> list[Task]:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="startDate must be on or before endDate.")
    if (completed_start_date is None) != (completed_end_date is None):
        raise HTTPException(
            status_code=400,
            detail="completedStartDate and completedEndDate must be supplied together.",
        )
    if completed_start_date and completed_end_date and completed_start_date > completed_end_date:
        raise HTTPException(
            status_code=400,
            detail="completedStartDate must be on or before completedEndDate.",
        )
    tasks = [
        task for task in load_tasks(storage)
        if start_date <= task.task_date <= end_date
    ]
    if status:
        tasks = [task for task in tasks if task.status == status]
    if completed_start_date and completed_end_date:
        tasks = [
            task for task in tasks
            if task.completed_at is not None
            and completed_start_date <= task.completed_at.astimezone(timezone()).date() <= completed_end_date
        ]
    return sorted(tasks, key=lambda task: (task.task_date, task.created_at))


@app.get(
    "/api/dashboard/summary",
    response_model=DashboardSummary,
    dependencies=[Depends(authorize)],
)
def dashboard_summary(storage: Annotated[SheetsStore, Depends(store)]) -> DashboardSummary:
    current_date = today()
    tasks = load_tasks(storage)
    pending = [task for task in tasks if task.status == TaskStatus.PENDING]
    on_hold = [task for task in tasks if task.status == TaskStatus.ON_HOLD]
    completed = [task for task in tasks if task.status == TaskStatus.COMPLETED]
    today_tasks = [task for task in pending if task.task_date == current_date]
    due_today = [task for task in pending if task.task_date == current_date]
    overdue = [task for task in pending if task.task_date < current_date]
    upcoming = [task for task in pending if task.task_date > current_date]
    return DashboardSummary(
        total=len(tasks),
        pending=len(pending),
        on_hold=len(on_hold),
        completed=len(completed),
        overdue=len(overdue),
        due_today=len(due_today),
        upcoming=len(upcoming),
        today_tasks=sorted(today_tasks, key=lambda task: task.priority.value),
        overdue_tasks=sorted(overdue, key=lambda task: task.task_date),
        upcoming_tasks=sorted(upcoming, key=lambda task: task.task_date)[:8],
    )
