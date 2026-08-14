"""Drift test: the tag prefixes in CONTRIBUTING.md must match the router in release.yml."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _documented_prefixes():
    section = CONTRIBUTING_MD.read_text().split("### Tag Prefixes")[1].split("###")[0]
    return set(re.findall(r"^\|[^|\n]+\|[^|\n]+\|\s*`([^`\n]+\*)`\s*\|", section, re.M))


def _routed_prefixes():
    case_block = re.search(r'case "\$TAG" in\n(.*?)\n\s*esac', RELEASE_YML.read_text(), re.S).group(1)
    return set(re.findall(r"^\s*([\w.-]+\*)\)", case_block, re.M))


def test_documented_prefixes_match_release_router():
    documented, routed = _documented_prefixes(), _routed_prefixes()
    assert documented, "CONTRIBUTING.md '### Tag Prefixes' table has no tag prefixes"
    assert documented == routed, (
        f"CONTRIBUTING.md documents {sorted(documented - routed)} with no arm in release.yml, "
        f"and release.yml routes {sorted(routed - documented)} with no row in CONTRIBUTING.md"
    )
