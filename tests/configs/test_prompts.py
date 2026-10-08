import re

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


def test_additive_prompt_example_numbers_are_sequential():
    example_numbers = re.findall(r"## Example (\d+):", prompts.ADDITIVE_EXTRACTION_PROMPT)
    assert example_numbers == [str(i) for i in range(1, len(example_numbers) + 1)]


def test_additive_prompt_text_includes_assistant_echo_example():
    prompt = prompts.ADDITIVE_EXTRACTION_PROMPT

    assert "Example 4: Skip Assistant Echoes of User Preferences" in prompt
    assert "not from the assistant's restatement" in prompt
    assert "do NOT add a duplicate memory" in prompt
    assert "Assistant will prioritize quiet wooden-floor venues" in prompt


def test_additive_prompt_builder_includes_user_and_assistant_echo_messages():
    new_messages = [
        {
            "role": "user",
            "content": "For badminton venues, I prefer quiet courts with wooden floors after 8 PM.",
        },
        {
            "role": "assistant",
            "content": "Got it. I will prioritize quiet wooden-floor venues after 8 PM.",
        },
    ]

    result = prompts.generate_additive_extraction_prompt(new_messages=new_messages)

    assert "## New Messages" in result
    assert "quiet courts with wooden floors after 8 PM" in result
    assert "I will prioritize quiet wooden-floor venues after 8 PM" in result
