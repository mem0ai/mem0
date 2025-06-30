import contextvars
from fastapi import BackgroundTasks

# Centralized context variables to be used across different modules.
# This avoids circular dependencies and keeps context management clean.

user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("supa_user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")
background_tasks_var: contextvars.ContextVar["BackgroundTasks"] = contextvars.ContextVar("background_tasks") 