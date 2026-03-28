from mem0.configs import prompts


def test_get_update_memory_messages():
    retrieved_old_memory_dict = [{"id": "1", "text": "old memory 1"}]
    response_content = ["new fact"]
    custom_update_memory_prompt = "custom prompt determining memory update"

    ## When custom update memory prompt is provided
    ##
    result = prompts.get_update_memory_messages(
        retrieved_old_memory_dict, response_content, custom_update_memory_prompt
    )
    assert result.startswith(custom_update_memory_prompt)

    ## When custom update memory prompt is not provided
    ##
    result = prompts.get_update_memory_messages(retrieved_old_memory_dict, response_content, None)
    assert result.startswith(prompts.DEFAULT_UPDATE_MEMORY_PROMPT)


def test_get_update_memory_messages_empty_memory():
    # Test with None for retrieved_old_memory_dict
    result = prompts.get_update_memory_messages(
        None, 
        ["new fact"], 
        None
    )
    assert "Current memory is empty" in result

    # Test with empty list for retrieved_old_memory_dict
    result = prompts.get_update_memory_messages(
        [], 
        ["new fact"], 
        None
    )
    assert "Current memory is empty" in result


def test_get_update_memory_messages_non_empty_memory():
    # Non-empty memory scenario
    memory_data = [{"id": "1", "text": "existing memory"}]
    result = prompts.get_update_memory_messages(
        memory_data, 
        ["new fact"], 
        None
    )
    # Check that the memory data is displayed
    assert str(memory_data) in result
    # And that the non-empty memory message is present
    assert "current content of my memory" in result


def test_default_update_memory_prompt_contradiction_includes_add():
    """Verify the update memory prompt instructs the LLM to ADD the new
    contradicting fact when DELETing the old one, preventing data loss."""
    prompt = prompts.DEFAULT_UPDATE_MEMORY_PROMPT

    # The DELETE section example should contain an ADD event for the
    # replacement fact so contradicting memories are not silently lost.
    assert '"event" : "ADD"' in prompt, (
        "DEFAULT_UPDATE_MEMORY_PROMPT must instruct the LLM to ADD the new "
        "fact when deleting a contradicting memory"
    )

    # The DELETE section should explicitly mention adding the new fact
    assert "add the new fact" in prompt.lower(), (
        "DELETE instructions should tell the LLM to add the new contradicting fact"
    )
