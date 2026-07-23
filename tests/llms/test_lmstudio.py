from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.llms.lmstudio import LMStudioLLM


def test_lmstudio_llm_base_url(monkeypatch):
    # case1: default is used when neither config nor env sets a base URL
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    llm = LMStudioLLM(LMStudioConfig(model="test-model"))
    assert str(llm.client.base_url) == "http://localhost:1234/v1/"

    # case2: LMSTUDIO_BASE_URL env is honored when config leaves it unset (#6526)
    env_base_url = "http://192.168.1.5:1234/v1/"
    monkeypatch.setenv("LMSTUDIO_BASE_URL", env_base_url)
    llm = LMStudioLLM(LMStudioConfig(model="test-model"))
    assert str(llm.client.base_url) == env_base_url

    # case3: explicit config base URL wins over the env var
    config_base_url = "http://config-host:9999/v1/"
    llm = LMStudioLLM(LMStudioConfig(model="test-model", lmstudio_base_url=config_base_url))
    assert str(llm.client.base_url) == config_base_url
