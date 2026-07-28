"""mem0-agent: coding-agent memory built on existing Mem0 platform APIs."""

from .config.project_config import DURABLE_TYPES, POLICY_VERSION, TYPES

__all__ = ["TYPES", "DURABLE_TYPES", "POLICY_VERSION", "__version__"]
__version__ = "0.1.0"
