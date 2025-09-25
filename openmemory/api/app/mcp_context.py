import contextvars

# Shared ContextVars for MCP tools. Kept in a dedicated module so that
# `importlib.reload(app.mcp_server)` during tests does not create new ContextVar
# objects and break references held by other tests.

user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

