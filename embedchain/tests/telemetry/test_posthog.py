import logging
import os

from embedchain.telemetry.posthog import AnonymousTelemetry


class TestAnonymousTelemetry:
    def test_init(self, mocker):
        # Enable telemetry specifically for this test
        os.environ["EC_TELEMETRY"] = "true"
        mock_posthog = mocker.patch("embedchain.telemetry.posthog.Posthog")
        telemetry = AnonymousTelemetry()
        assert telemetry.project_api_key == "phc_PHQDA5KwztijnSojsxJ2c1DuJd52QCzJzT2xnSGvjN2"
        assert telemetry.host == "https://app.posthog.com"
        assert telemetry.enabled is True
        assert telemetry.user_id
        mock_posthog.assert_called_once_with(project_api_key=telemetry.project_api_key, host=telemetry.host)

    def test_init_with_disabled_telemetry(self, mocker):
        mocker.patch("embedchain.telemetry.posthog.Posthog")
        telemetry = AnonymousTelemetry()
        assert telemetry.enabled is False
        assert telemetry.posthog.disabled is True

    def test_get_user_id(self, mocker, tmpdir):
        mock_uuid = mocker.patch("embedchain.telemetry.posthog.uuid.uuid4")
        mock_uuid.return_value = "unique_user_id"
        config_file = tmpdir.join("config.json")
        mocker.patch("embedchain.telemetry.posthog.CONFIG_FILE", str(config_file))
        telemetry = AnonymousTelemetry()

        user_id = telemetry._get_user_id()
        assert user_id == "unique_user_id"
        assert config_file.read() == '{"user_id": "unique_user_id"}'

    def test_capture(self, mocker):
        # Enable telemetry specifically for this test
        os.environ["EC_TELEMETRY"] = "true"
        mock_posthog = mocker.patch("embedchain.telemetry.posthog.Posthog")
        telemetry = AnonymousTelemetry()
        event_name = "test_event"
        properties = {"key": "value"}
        telemetry.capture(event_name, properties)

        mock_posthog.assert_called_once_with(
            project_api_key=telemetry.project_api_key,
            host=telemetry.host,
        )
        mock_posthog.return_value.capture.assert_called_once_with(
            telemetry.user_id,
            event_name,
            properties,
        )

    def test_capture_with_exception(self, mocker, caplog):
        os.environ["EC_TELEMETRY"] = "true"
        mock_posthog = mocker.patch("embedchain.telemetry.posthog.Posthog")
        mock_posthog.return_value.capture.side_effect = Exception("Test Exception")
        telemetry = AnonymousTelemetry()
        event_name = "test_event"
        properties = {"key": "value"}
        with caplog.at_level(logging.ERROR):
            telemetry.capture(event_name, properties)
        assert "Failed to send telemetry event" in caplog.text
        caplog.clear()
