def generate_error_message_for_api_keys(error: ValueError) -> str:
    env_mapping = {
        "OPENAI_API_KEY": "OPENAI_API_KEY",
        "OPENAI_API_TYPE": "OPENAI_API_TYPE",
        "OPENAI_API_BASE": "OPENAI_API_BASE",
        "OPENAI_API_VERSION": "OPENAI_API_VERSION",
        "COHERE_API_KEY": "COHERE_API_KEY",
        "TOGETHER_API_KEY": "TOGETHER_API_KEY",
        "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
        "JINACHAT_API_KEY": "JINACHAT_API_KEY",
        "HUGGINGFACE_ACCESS_TOKEN": "HUGGINGFACE_ACCESS_TOKEN",
        "REPLICATE_API_TOKEN": "REPLICATE_API_TOKEN",
    }

    missing_keys = [env_mapping[key] for key in env_mapping if key in str(error)]
    if missing_keys:
        missing_keys_str = ", ".join(missing_keys)
        return f"""Please set the {missing_keys_str} environment variable(s) when running the Docker container.
Example: `docker run -e {missing_keys[0]}=xxx embedchain/rest-api:latest`
"""
    else:
        return "Error: " + str(error)
