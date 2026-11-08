import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_file: Path
    run: Path


PROVIDERS = {
    "zhizengzeng": Provider(
        name="zhizengzeng",
        base_url="https://api.zhizengzeng.com/v1",
        key_file=ROOT.parent / ".venv" / "zhizengzeng.key",
        run=ROOT / "locomo-pilot-conv0",
    ),
    "openai": Provider(
        name="openai",
        base_url="https://api.openai.com/v1",
        key_file=ROOT.parent / ".venv" / "openai.key",
        run=ROOT / "locomo-pilot-conv0-openai",
    ),
}


def configure_provider(name):
    provider = PROVIDERS[name]
    key = provider.key_file.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError(f"API key file is empty: {provider.key_file}")
    os.environ["MEM0_TELEMETRY"] = "false"
    os.environ["MEM0_DIR"] = str(provider.run / "mem0-home")
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = provider.base_url
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ.pop("OPENAI_API_BASE", None)
    return provider, key


def validate_provider(data, name):
    recorded = data.get("provider")
    if recorded != name and not (recorded is None and name == "zhizengzeng"):
        raise RuntimeError(f"Saved state provider {recorded!r} does not match {name!r}")
