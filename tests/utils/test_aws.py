import pytest
from botocore.config import Config

from mem0.utils.aws import build_boto_client_config


class TestBuildBotoClientConfig:
    def test_all_none_returns_none(self):
        # Opt-in invariant: nothing configured -> None -> caller omits config=
        assert build_boto_client_config() is None

    def test_scalars_only_builds_config(self):
        cfg = build_boto_client_config(read_timeout=300, connect_timeout=10)
        assert cfg is not None
        assert cfg.read_timeout == 300
        assert cfg.connect_timeout == 10

    def test_dict_base_expanded(self):
        cfg = build_boto_client_config(boto_client_config={"retries": {"mode": "adaptive", "max_attempts": 5}})
        assert cfg.retries == {"mode": "adaptive", "max_attempts": 5}

    def test_config_object_passthrough(self):
        # Config(**a_Config_instance) would raise TypeError; the helper must branch.
        base = Config(read_timeout=77, retries={"mode": "standard"})
        cfg = build_boto_client_config(boto_client_config=base)
        assert cfg.read_timeout == 77
        assert cfg.retries == {"mode": "standard"}

    def test_scalars_override_base_preserves_other_keys(self):
        cfg = build_boto_client_config(
            boto_client_config={"read_timeout": 999, "max_pool_connections": 20},
            read_timeout=120,
        )
        assert cfg.read_timeout == 120  # scalar wins on its key
        assert cfg.max_pool_connections == 20  # base's other keys preserved

    def test_config_only_timeout_not_clobbered(self):
        # REGRESSION TEST for the design bug: base sets read_timeout, scalars unset.
        # Naive base.merge(Config(read_timeout=None)) would null it to None.
        cfg = build_boto_client_config(boto_client_config={"read_timeout": 300})
        assert cfg.read_timeout == 300

    @pytest.mark.parametrize("bad", [0, -5, -0.5, "abc", True])
    def test_non_positive_or_nonnumeric_timeout_raises(self, bad):
        with pytest.raises(ValueError, match="read_timeout"):
            build_boto_client_config(read_timeout=bad)

    def test_connect_timeout_validation(self):
        with pytest.raises(ValueError, match="connect_timeout"):
            build_boto_client_config(connect_timeout=-1)

    def test_malformed_dict_unknown_key_wrapped(self):
        with pytest.raises(ValueError, match="Invalid boto_client_config"):
            build_boto_client_config(boto_client_config={"reda_timeout": 5})

    def test_malformed_dict_bad_subdict_wrapped(self):
        with pytest.raises(ValueError, match="Invalid boto_client_config"):
            build_boto_client_config(boto_client_config={"retries": {"bad_option": 1}})

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="must be a botocore.config.Config or dict"):
            build_boto_client_config(boto_client_config=12345)
