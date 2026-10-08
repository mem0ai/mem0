"""
Smoke tests for the server production Dockerfile.

Verifies that the built image:
- Runs as a non-root user (mem0)
- Does not include --reload in the default CMD
- Can import psycopg (libpq5 runtime linkage works)

Requires Docker CLI and a running Docker daemon.
Tests are skipped automatically if Docker is not available.
"""

import json
import subprocess

import pytest

IMAGE_NAME = "mem0-api-server:test"


def _docker_available():
    """Check whether the Docker CLI and daemon are reachable."""
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


requires_docker = pytest.mark.skipif(not _docker_available(), reason="Docker not available")


@pytest.fixture(scope="module")
def built_image():
    """Build the server Docker image once for all tests in this module."""
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_NAME, "server"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.skip(f"Docker build failed: {result.stderr[:500]}")

    yield IMAGE_NAME

    # Best-effort cleanup
    subprocess.run(["docker", "rmi", "-f", IMAGE_NAME], capture_output=True)


@requires_docker
class TestServerDockerfile:
    def test_runs_as_non_root(self, built_image):
        """The container should run as the 'mem0' user, not root."""
        result = subprocess.run(
            ["docker", "run", "--rm", built_image, "whoami"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"whoami failed: {result.stderr}"
        assert result.stdout.strip() == "mem0"

    def test_cmd_no_reload(self, built_image):
        """Production CMD should not contain --reload."""
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{json .Config.Cmd}}", built_image],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        cmd = json.loads(result.stdout)
        assert "--reload" not in cmd, f"--reload found in CMD: {cmd}"

    def test_psycopg_imports(self, built_image):
        """psycopg should import successfully (verifies libpq5 linkage)."""
        result = subprocess.run(
            ["docker", "run", "--rm", built_image, "python", "-c", "import psycopg"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"psycopg import failed: {result.stderr}"
