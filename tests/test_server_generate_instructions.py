from server.parsing import parse_generate_instructions_response


def test_parse_generate_instructions_preserves_recurring_markers():
    response = (
        "INSTRUCTIONS: Please follow these INSTRUCTIONS: prioritize recent events.\n"
        "TEST_MESSAGE: This is a TEST_MESSAGE: hello."
    )

    instructions, test_message = parse_generate_instructions_response(response)

    assert instructions == "Please follow these INSTRUCTIONS: prioritize recent events."
    assert test_message == "This is a TEST_MESSAGE: hello."
