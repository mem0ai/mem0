from mem0.memory.main import _safe_deepcopy_config


class FailingDeepcopyConfig:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __deepcopy__(self, memo):
        raise RuntimeError("deepcopy not supported")


class ModelDumpConfig:
    def __init__(self, **kwargs):
        self.model_dump_called = False
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __deepcopy__(self, memo):
        raise RuntimeError("deepcopy not supported")

    def model_dump(self, mode="json"):
        self.model_dump_called = True
        return {
            "api_key": self.api_key,
            "secret_token": self.secret_token,
            "normal": self.normal,
        }


def test_safe_deepcopy_config_redacts_sensitive_fields():
    config = FailingDeepcopyConfig(
        api_key="secret-key",
        password="pass",
        connection_class="cls",
        normal="ok",
    )

    clone = _safe_deepcopy_config(config)

    assert clone.api_key is None
    assert clone.password is None
    assert clone.connection_class is None
    assert clone.normal == "ok"
    assert config.api_key == "secret-key"


def test_safe_deepcopy_config_uses_model_dump_when_available():
    config = ModelDumpConfig(
        api_key="secret-key",
        secret_token="secret-token",
        normal="ok",
    )

    clone = _safe_deepcopy_config(config)

    assert config.model_dump_called is True
    assert clone.api_key is None
    assert clone.secret_token is None
    assert clone.normal == "ok"
