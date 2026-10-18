from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"


def calculate_task_state(status: TaskStatus, task_date: date, current_date: date) -> str:
    if status == TaskStatus.COMPLETED:
        return "COMPLETED"
    if status == TaskStatus.ON_HOLD:
        return "ON_HOLD"
    if task_date < current_date:
        return "OVERDUE"
    if task_date == current_date:
        return "DUE_TODAY"
    return "UPCOMING"


class TaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    task_date: date
    priority: Priority = Priority.MEDIUM

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title is required.")
        return value


class TaskUpdate(TaskInput):
    pass


class Task(BaseModel):
    task_id: str
    title: str
    description: str
    task_date: date
    priority: Priority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    deleted: bool = False
    state: str


class DashboardSummary(BaseModel):
    total: int
    pending: int
    on_hold: int
    completed: int
    overdue: int
    due_today: int
    upcoming: int
    today_tasks: list[Task]
    overdue_tasks: list[Task]
    upcoming_tasks: list[Task]
