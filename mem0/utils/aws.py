from typing import TYPE_CHECKING, Dict, Optional, Union

if TYPE_CHECKING:
    from botocore.config import Config


def build_boto_client_config(
    boto_client_config: Optional[Union["Config", Dict]] = None,
    read_timeout: Optional[float] = None,
    connect_timeout: Optional[float] = None,
) -> Optional["Config"]:
    """Build a botocore Config from a base config plus convenience timeout scalars.

    Returns ``None`` when nothing is configured, so callers omit ``config=`` and
    behavior is identical to botocore defaults (opt-in).

    ``boto_client_config`` accepts a ready ``botocore.config.Config`` OR a plain dict
    of Config kwargs (e.g. ``{"retries": {"mode": "adaptive", "max_attempts": 5}}``)
    so callers can tune retries/pooling without importing botocore. ``read_timeout`` /
    ``connect_timeout`` are convenience scalars; when set they OVERRIDE the same key
    in ``boto_client_config``.

    Raises:
        ValueError: if a timeout scalar is non-positive/non-numeric, or if
            ``boto_client_config`` is malformed or an unsupported type.
    """
    # Fast path: nothing configured -> no Config, no botocore import needed.
    if boto_client_config is None and read_timeout is None and connect_timeout is None:
        return None

    # Lazy import keeps this module importable without the AWS extra.
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError

    # 1. Validate scalars. None == unset; 0/negative/non-number == invalid.
    #    bool is excluded explicitly (bool is a subclass of int).
    for name, val in (("read_timeout", read_timeout), ("connect_timeout", connect_timeout)):
        if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0):
            raise ValueError(f"{name} must be a positive number, got {val!r}")

    # 2. Normalize the base. MUST branch: Config(**a_Config_instance) raises TypeError.
    if boto_client_config is None:
        base = None
    elif isinstance(boto_client_config, Config):
        base = boto_client_config
    elif isinstance(boto_client_config, dict):
        try:
            base = Config(**boto_client_config)
        except (TypeError, BotoCoreError) as e:  # unknown key -> TypeError; bad sub-dict -> BotoCoreError
            raise ValueError(f"Invalid boto_client_config: {e}") from e
    else:
        raise ValueError(
            f"boto_client_config must be a botocore.config.Config or dict, got {type(boto_client_config).__name__}"
        )

    # 3. Build the scalar override from ONLY set keys (never pass None into Config —
    #    that would clobber the base via merge). Empty overrides -> return base as-is.
    overrides = {
        k: v for k, v in (("read_timeout", read_timeout), ("connect_timeout", connect_timeout)) if v is not None
    }
    if not overrides:
        return base
    override_cfg = Config(**overrides)
    return override_cfg if base is None else base.merge(override_cfg)
