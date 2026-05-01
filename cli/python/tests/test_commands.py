"""Tests for CLI commands using mock backend."""

from __future__ import annotations

import json
import typing
from io import StringIO
from unittest.mock import patch

import pytest
from click.exceptions import Exit as ClickExit
from rich.console import Console

from mem0_cli.commands.config_cmd import (
    cmd_config_get,
    cmd_config_set,
    cmd_config_show,
)
from mem0_cli.commands.entities import cmd_entities_delete, cmd_entities_list
from mem0_cli.commands.events_cmd import cmd_event_list, cmd_event_status
from mem0_cli.commands.memory import (
    cmd_add,
    cmd_delete,
    cmd_delete_all,
    cmd_get,
    cmd_list,
    cmd_search,
    cmd_update,
)
from mem0_cli.commands.utils import (
    cmd_import,
    cmd_status,
)


def _make_console():
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True, width=120), buf


def _make_err_console():
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True, width=120), buf


class TestAddCommand:
    def test_add_text(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "I prefer dark mode",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )
        mock_backend.add.assert_called_once()

    def test_add_with_messages(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        msgs = json.dumps([{"role": "user", "content": "I love Python"}])
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                None,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=msgs,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )
        mock_backend.add.assert_called_once()

    def test_add_with_metadata(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "test memory",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata='{"source": "test"}',
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )
        call_kwargs = mock_backend.add.call_args
        assert "metadata" in str(call_kwargs)

    def test_add_json_output(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="json",
            )
        output = buf.getvalue()
        assert '"results"' in output or '"memory"' in output

    def test_add_quiet_output(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="quiet",
            )
        output = buf.getvalue()
        # In quiet mode, no memory content should be printed (spinner may appear)
        assert "dark mode" not in output

    def test_add_no_content_exits(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
            patch("mem0_cli.commands.memory._stdin_is_piped", return_value=False),
            pytest.raises((SystemExit, ClickExit)),
        ):
            cmd_add(
                mock_backend,
                None,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )

    def test_add_invalid_metadata_json(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
            pytest.raises((SystemExit, ClickExit)),
        ):
            cmd_add(
                mock_backend,
                "test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata="not-json",
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )

    def test_add_from_file(self, mock_backend, tmp_path):
        file_path = tmp_path / "messages.json"
        file_path.write_text(json.dumps([{"role": "user", "content": "hello"}]))
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                None,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=file_path,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )
        mock_backend.add.assert_called_once()

    def test_add_categories_csv(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories="health,prefs",
                output="text",
            )
        mock_backend.add.assert_called_once()


class TestAddDeduplicatesPending:
    """Ensure duplicate PENDING entries with the same event_id are collapsed."""

    DUPLICATE_PENDING: typing.ClassVar[dict] = {
        "results": [
            {"status": "PENDING", "event_id": "evt-dup"},
            {"status": "PENDING", "event_id": "evt-dup"},
        ]
    }

    def _run_add(self, mock_backend, output):
        mock_backend.add.return_value = self.DUPLICATE_PENDING
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output=output,
            )
        return buf.getvalue()

    def test_text_shows_one_pending(self, mock_backend):
        raw = self._run_add(mock_backend, "text")
        assert raw.count("Queued") == 1

    def test_json_shows_one_pending(self, mock_backend):
        raw = self._run_add(mock_backend, "json")
        data = json.loads(raw)
        results = data.get("results", data)
        pending = [r for r in results if r.get("status") == "PENDING"]
        assert len(pending) == 1

    def test_agent_shows_one_pending(self, mock_backend):
        from mem0_cli.state import set_agent_mode

        set_agent_mode(True)
        try:
            raw = self._run_add(mock_backend, "agent")
        finally:
            set_agent_mode(False)
        data = json.loads(raw)
        assert data["count"] == 1
        assert len(data["data"]) == 1


class TestSearchCommand:
    def test_search_text(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_search(
                mock_backend,
                "preferences",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=10,
                threshold=0.3,
                rerank=False,
                keyword=False,
                filter_json=None,
                fields=None,
                output="text",
            )
        output = buf.getvalue()
        assert "Found 2" in output

    def test_search_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_search(
                mock_backend,
                "preferences",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=10,
                threshold=0.3,
                rerank=False,
                keyword=False,
                filter_json=None,
                fields=None,
                output="json",
            )
        output = buf.getvalue()
        assert '"memory"' in output

    def test_search_table(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_search(
                mock_backend,
                "preferences",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=10,
                threshold=0.3,
                rerank=False,
                keyword=False,
                filter_json=None,
                fields=None,
                output="table",
            )
        output = buf.getvalue()
        assert "dark mode" in output

    def test_search_no_results(self, mock_backend):
        mock_backend.search.return_value = []
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_search(
                mock_backend,
                "nonexistent",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=10,
                threshold=0.3,
                rerank=False,
                keyword=False,
                filter_json=None,
                fields=None,
                output="text",
            )
        output = buf.getvalue()
        assert "No memories found" in output

    def test_search_with_filter(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_search(
                mock_backend,
                "test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=5,
                threshold=0.5,
                rerank=False,
                keyword=False,
                filter_json='{"category": "prefs"}',
                fields="memory,score",
                output="text",
            )
        mock_backend.search.assert_called_once()


class TestGetCommand:
    def test_get_text(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_get(mock_backend, "abc-123-def-456", output="text")
        output = buf.getvalue()
        assert "dark mode" in output
        assert "abc-123-def-456" in output

    def test_get_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_get(mock_backend, "abc-123-def-456", output="json")
        output = buf.getvalue()
        assert '"memory"' in output


class TestListCommand:
    def test_list_table(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_list(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                page=1,
                page_size=100,
                category=None,
                after=None,
                before=None,
                output="table",
            )
        output = buf.getvalue()
        assert "dark mode" in output

    def test_list_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_list(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                page=1,
                page_size=100,
                category=None,
                after=None,
                before=None,
                output="json",
            )
        output = buf.getvalue()
        assert '"memory"' in output

    def test_list_empty(self, mock_backend):
        mock_backend.list_memories.return_value = []
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_list(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                page=1,
                page_size=100,
                category=None,
                after=None,
                before=None,
                output="text",
            )
        output = buf.getvalue()
        assert "No memories found" in output


class TestUpdateCommand:
    def test_update(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_update(mock_backend, "abc-123", "New text", metadata=None, output="text")
        output = buf.getvalue()
        assert "updated" in output.lower()

    def test_update_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_update(mock_backend, "abc-123", "New text", metadata=None, output="json")
        output = buf.getvalue()
        assert '"memory"' in output


class TestDeleteCommand:
    def test_delete_single(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete(mock_backend, "abc-123", output="text")
        output = buf.getvalue()
        assert "deleted" in output.lower()

    def test_delete_dry_run(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete(mock_backend, "abc-123-def-456", dry_run=True, output="text")
        output = buf.getvalue()
        assert "dry run" in output.lower()
        mock_backend.delete.assert_not_called()


class TestDeleteAllCommand:
    def test_delete_all_force(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete_all(
                mock_backend,
                force=True,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                output="text",
            )
        output = buf.getvalue()
        assert "deleted" in output.lower()

    def test_delete_all_dry_run(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete_all(
                mock_backend,
                force=True,
                dry_run=True,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                output="text",
            )
        output = buf.getvalue()
        assert "dry run" in output.lower()
        mock_backend.delete.assert_not_called()

    def test_delete_all_project_wide(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete_all(
                mock_backend,
                force=True,
                all_=True,
                user_id=None,
                agent_id=None,
                app_id=None,
                run_id=None,
                output="text",
            )
        mock_backend.delete.assert_called_once_with(
            all=True,
            user_id="*",
            agent_id="*",
            app_id="*",
            run_id="*",
        )

    def test_delete_all_project_wide_async_response(self, mock_backend):
        mock_backend.delete.return_value = {"message": "Memories deletion started..."}
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete_all(
                mock_backend,
                force=True,
                all_=True,
                user_id=None,
                agent_id=None,
                app_id=None,
                run_id=None,
                output="text",
            )
        output = buf.getvalue()
        assert "background" in output.lower()


class TestStatusCommand:
    def test_status_connected(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.utils.console", console),
            patch("mem0_cli.commands.utils.err_console", err_console),
        ):
            cmd_status(mock_backend)
        output = buf.getvalue()
        assert "Connected" in output

    def test_status_disconnected(self, mock_backend):
        mock_backend.status.return_value = {
            "connected": False,
            "backend": "platform",
            "error": "Connection refused",
        }
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.utils.console", console),
            patch("mem0_cli.commands.utils.err_console", err_console),
        ):
            cmd_status(mock_backend)
        output = buf.getvalue()
        assert "Disconnected" in output
        assert "Connection refused" in output

    def test_status_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.utils.console", console),
            patch("mem0_cli.commands.utils.err_console", err_console),
        ):
            cmd_status(mock_backend, output="json")
        output = buf.getvalue()
        assert '"connected"' in output
        assert '"status"' in output


class TestImportCommand:
    def test_import_json(self, mock_backend, tmp_path):
        file_path = tmp_path / "import.json"
        data = [
            {"memory": "Test memory 1"},
            {"memory": "Test memory 2"},
        ]
        file_path.write_text(json.dumps(data))
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.utils.console", console),
            patch("mem0_cli.commands.utils.err_console", err_console),
        ):
            cmd_import(mock_backend, str(file_path), user_id="alice", agent_id=None)
        assert mock_backend.add.call_count == 2

    def test_import_invalid_file(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.utils.console", console),
            patch("mem0_cli.commands.utils.err_console", err_console),
            pytest.raises((SystemExit, ClickExit)),
        ):
            cmd_import(mock_backend, "/nonexistent/file.json", user_id=None, agent_id=None)

    def test_import_json_output(self, mock_backend, tmp_path):
        file_path = tmp_path / "import.json"
        data = [{"memory": "Test memory 1"}]
        file_path.write_text(json.dumps(data))
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.utils.console", console),
            patch("mem0_cli.commands.utils.err_console", err_console),
        ):
            cmd_import(mock_backend, str(file_path), user_id="alice", agent_id=None, output="json")
        output = buf.getvalue()
        assert '"added"' in output


class TestEntitiesListCommand:
    def test_list_users(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
        ):
            cmd_entities_list(mock_backend, "users", output="table")
        output = buf.getvalue()
        assert "alice" in output

    def test_list_invalid_type(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
            pytest.raises((SystemExit, ClickExit)),
        ):
            cmd_entities_list(mock_backend, "invalid", output="table")

    def test_list_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
        ):
            cmd_entities_list(mock_backend, "users", output="json")
        output = buf.getvalue()
        assert '"alice"' in output


class TestConfigCommands:
    def test_config_show(self, isolate_config):
        from mem0_cli.config import Mem0Config, save_config

        config = Mem0Config()
        config.platform.api_key = "m0-test12345678"
        save_config(config)

        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.config_cmd.console", console),
            patch("mem0_cli.commands.config_cmd.err_console", err_console),
        ):
            cmd_config_show()
        output = buf.getvalue()
        assert "Configuration" in output
        assert "m0-test12345678" not in output

    def test_config_show_json(self, isolate_config):
        from mem0_cli.config import Mem0Config, save_config

        config = Mem0Config()
        config.platform.api_key = "m0-test12345678"
        config.defaults.user_id = "alice"
        save_config(config)

        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.config_cmd.console", console),
            patch("mem0_cli.commands.config_cmd.err_console", err_console),
        ):
            cmd_config_show(output="json")
        output = buf.getvalue()
        assert '"status"' in output
        assert '"config show"' in output

    def test_config_set_and_get(self, isolate_config):
        console1, _buf1 = _make_console()
        err_console1, _err_buf1 = _make_err_console()
        with (
            patch("mem0_cli.commands.config_cmd.console", console1),
            patch("mem0_cli.commands.config_cmd.err_console", err_console1),
        ):
            cmd_config_set("platform.base_url", "https://custom.api.mem0.ai")

        console2, buf2 = _make_console()
        err_console2, _err_buf2 = _make_err_console()
        with (
            patch("mem0_cli.commands.config_cmd.console", console2),
            patch("mem0_cli.commands.config_cmd.err_console", err_console2),
        ):
            cmd_config_get("platform.base_url")
        output = buf2.getvalue()
        assert "custom.api.mem0.ai" in output

    def test_config_show_displays_defaults(self, isolate_config):
        from mem0_cli.config import Mem0Config, save_config

        config = Mem0Config()
        config.defaults.user_id = "alice"
        save_config(config)

        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.config_cmd.console", console),
            patch("mem0_cli.commands.config_cmd.err_console", err_console),
        ):
            cmd_config_show()
        output = buf.getvalue()
        assert "defaults.user_id" in output
        assert "alice" in output


class TestEntitiesDeleteCommand:
    def test_delete_entity_with_force(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
        ):
            cmd_entities_delete(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                force=True,
                output="text",
            )
        mock_backend.delete_entities.assert_called_once_with(
            user_id="alice", agent_id=None, app_id=None, run_id=None
        )
        output = buf.getvalue()
        assert "deleted" in output.lower()

    def test_delete_entity_agent_id(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
        ):
            cmd_entities_delete(
                mock_backend,
                user_id=None,
                agent_id="bot1",
                app_id=None,
                run_id=None,
                force=True,
                output="text",
            )
        mock_backend.delete_entities.assert_called_once_with(
            user_id=None, agent_id="bot1", app_id=None, run_id=None
        )
        output = buf.getvalue()
        assert "deleted" in output.lower()

    def test_delete_entity_no_id_exits(self, mock_backend):
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
            pytest.raises((SystemExit, ClickExit)),
        ):
            cmd_entities_delete(
                mock_backend,
                user_id=None,
                agent_id=None,
                app_id=None,
                run_id=None,
                force=True,
                output="text",
            )

    def test_delete_entity_json_output(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
        ):
            cmd_entities_delete(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                force=True,
                output="json",
            )
        output = buf.getvalue()
        assert '"message"' in output

    def test_delete_entity_dry_run(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.entities.console", console),
            patch("mem0_cli.commands.entities.err_console", err_console),
        ):
            cmd_entities_delete(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                force=True,
                dry_run=True,
                output="text",
            )
        output = buf.getvalue()
        assert "dry run" in output.lower()
        mock_backend.delete_entities.assert_not_called()


class TestEventCommands:
    def test_event_list_table(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_list(mock_backend, output="table")
        out = buf.getvalue()
        assert "evt-abc-" in out
        assert "ADD" in out
        assert "SUCCEEDED" in out

    def test_event_list_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_list(mock_backend, output="json")
        out = buf.getvalue()
        assert "evt-abc-123-def-456" in out
        assert "evt-def-456-ghi-789" in out

    def test_event_list_empty(self, mock_backend):
        mock_backend.list_events.return_value = []
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_list(mock_backend, output="table")
        out = buf.getvalue()
        assert "No events" in out

    def test_event_status_text(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_status(mock_backend, "evt-abc-123-def-456", output="text")
        out = buf.getvalue()
        assert "evt-abc-123-def-456" in out
        assert "SUCCEEDED" in out

    def test_event_status_json(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_status(mock_backend, "evt-abc-123-def-456", output="json")
        out = buf.getvalue()
        assert "evt-abc-123-def-456" in out
        assert "ADD" in out


class TestAgentMode:
    """Tests for --json/--agent mode: structured JSON envelope output."""

    def setup_method(self):
        """Enable agent mode before each test."""
        from mem0_cli.state import set_agent_mode

        set_agent_mode(True)

    def teardown_method(self):
        """Reset agent mode after each test."""
        from mem0_cli.state import set_agent_mode

        set_agent_mode(False)

    # ── add ──────────────────────────────────────────────────────────────────

    def test_add_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "I prefer dark mode",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",  # will be overridden to "agent"
            )
        raw = buf.getvalue()
        data = json.loads(raw)
        assert data["status"] == "success"
        assert data["command"] == "add"
        assert "data" in data
        assert isinstance(data["data"], list)
        assert data["count"] == 1
        assert set(data["data"][0].keys()) == {"id", "memory", "event"}

    def test_add_agent_mode_scope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "test",
                user_id="bob",
                agent_id="agent1",
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )
        data = json.loads(buf.getvalue())
        assert data["scope"]["user_id"] == "bob"
        assert data["scope"]["agent_id"] == "agent1"

    # ── search ───────────────────────────────────────────────────────────────

    def test_search_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_search(
                mock_backend,
                "dark mode",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=10,
                threshold=0.3,
                rerank=False,
                keyword=False,
                filter_json=None,
                fields=None,
                output="text",
            )
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "search"
        assert isinstance(data["data"], list)
        assert data["count"] == 2
        assert "duration_ms" in data
        assert set(data["data"][0].keys()) == {"id", "memory", "score", "created_at", "categories"}

    # ── list ─────────────────────────────────────────────────────────────────

    def test_list_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_list(
                mock_backend,
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                page=1,
                page_size=100,
                category=None,
                after=None,
                before=None,
                output="table",  # will be overridden to "agent"
            )
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "list"
        assert isinstance(data["data"], list)
        assert data["count"] == 2
        assert data["scope"]["user_id"] == "alice"
        assert set(data["data"][0].keys()) == {"id", "memory", "created_at", "categories"}

    # ── get ──────────────────────────────────────────────────────────────────

    def test_get_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_get(mock_backend, "abc-123-def-456", output="text")
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "get"
        assert isinstance(data["data"], dict)
        assert data["data"]["id"] == "abc-123-def-456"
        assert "memory" in data["data"]
        assert set(data["data"].keys()) >= {"id", "memory"}

    # ── update ───────────────────────────────────────────────────────────────

    def test_update_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_update(mock_backend, "abc-123", "Updated content", metadata=None, output="text")
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "update"
        assert isinstance(data["data"], dict)
        assert "memory" in data["data"]
        assert "duration_ms" in data

    # ── delete ───────────────────────────────────────────────────────────────

    def test_delete_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_delete(mock_backend, "abc-123-def-456", output="text")
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "delete"
        assert data["data"]["id"] == "abc-123-def-456"
        assert data["data"]["deleted"] is True
        assert "duration_ms" in data

    # ── event list ───────────────────────────────────────────────────────────

    def test_event_list_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_list(mock_backend, output="table")
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "event list"
        assert isinstance(data["data"], list)
        assert data["count"] == 2
        assert "duration_ms" in data
        assert set(data["data"][0].keys()) == {
            "id",
            "event_type",
            "status",
            "latency",
            "created_at",
        }

    # ── event status ─────────────────────────────────────────────────────────

    def test_event_status_agent_mode_envelope(self, mock_backend):
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.events_cmd.console", console),
            patch("mem0_cli.commands.events_cmd.err_console", err_console),
        ):
            cmd_event_status(mock_backend, "evt-abc-123-def-456", output="text")
        data = json.loads(buf.getvalue())
        assert data["status"] == "success"
        assert data["command"] == "event status"
        assert isinstance(data["data"], dict)
        assert data["data"]["id"] == "evt-abc-123-def-456"
        assert "duration_ms" in data
        assert set(data["data"]["results"][0].keys()) == {"id", "event", "user_id", "memory"}
        assert "data" not in data["data"]["results"][0]

    # ── error handling ───────────────────────────────────────────────────────

    def test_error_in_agent_mode_produces_json_to_stdout(self, mock_backend):
        """Errors in agent mode must emit a JSON envelope to stdout, not stderr."""
        from io import StringIO

        mock_backend.get.side_effect = Exception("Memory not found")
        console, _buf = _make_console()
        err_console, _err_buf = _make_err_console()

        captured_stdout = StringIO()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
            patch("sys.stdout", captured_stdout),
            pytest.raises((SystemExit, ClickExit)),
        ):
            cmd_get(mock_backend, "bad-id", output="text")

        stdout_output = captured_stdout.getvalue()
        # The error JSON envelope must be on stdout
        error_data = json.loads(stdout_output)
        assert error_data["status"] == "error"
        assert "error" in error_data
        assert error_data["data"] is None

    def test_branding_suppressed_in_agent_mode(self, mock_backend):
        """Scope line and success message must be absent in agent mode output."""
        console, buf = _make_console()
        err_console, _err_buf = _make_err_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console),
        ):
            cmd_add(
                mock_backend,
                "branding test",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                messages=None,
                file=None,
                metadata=None,
                immutable=False,
                no_infer=False,
                expires=None,
                categories=None,
                output="text",
            )
        output = buf.getvalue()
        # Must be valid JSON only — no human-readable branding
        data = json.loads(output)
        assert data["status"] == "success"
        # "Scope:" and "Memory processed" must NOT appear in the raw output
        assert "Scope:" not in output
        assert "Memory processed" not in output
        assert "spinner" not in output.lower()

    def test_no_spinner_in_agent_mode(self, mock_backend):
        """timed_status must not emit spinner output in agent mode."""
        err_buf = StringIO()
        err_console_buf = Console(file=err_buf, force_terminal=False, no_color=True, width=120)
        console, _buf = _make_console()
        with (
            patch("mem0_cli.commands.memory.console", console),
            patch("mem0_cli.commands.memory.err_console", err_console_buf),
        ):
            cmd_search(
                mock_backend,
                "query",
                user_id="alice",
                agent_id=None,
                app_id=None,
                run_id=None,
                top_k=5,
                threshold=0.3,
                rerank=False,
                keyword=False,
                filter_json=None,
                fields=None,
                output="text",
            )
        # The err_buf captures what would have been spinner/timing noise
        # In agent mode it should be empty (no status lines printed)
        err_output = err_buf.getvalue()
        assert "Searching" not in err_output
