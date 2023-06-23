import re


def clean_string(text):
    text = text.replace('\n', ' ')
    cleaned_text = re.sub(r'\s+', ' ', text.strip())
    cleaned_text = cleaned_text.replace('\\', '')
    cleaned_text = cleaned_text.replace('#', ' ')
    cleaned_text = re.sub(r'([^\w\s])\1*', r'\1', cleaned_text)
    return cleaned_text

def markdown_to_plaintext(markdown_string):
    # Lines surrounded by empty lines are considered paragraph text
    markdown_string = markdown_string.strip().replace("\n\n", "\n")

    # Headers
    markdown_string = markdown_string.replace("# ", "")
    markdown_string = markdown_string.replace("## ", "")
    markdown_string = markdown_string.replace("### ", "")

    # Bold text
    markdown_string = markdown_string.replace("**", "")
    markdown_string = markdown_string.replace("__", "")

    # Italicized text
    markdown_string = markdown_string.replace("*", "")
    markdown_string = markdown_string.replace("_", "")

    # Ordered lists
    markdown_string = markdown_string.replace("1. ", "")
    markdown_string = markdown_string.replace("2. ", "")
    markdown_string = markdown_string.replace("3. ", "")
    # And so on for other numbers

    # Unordered lists
    markdown_string = markdown_string.replace("- ", "")
    markdown_string = markdown_string.replace("* ", "")
    markdown_string = markdown_string.replace("+ ", "")

    # Links and images
    while ("[" in markdown_string and "]" in markdown_string and 
           "(" in markdown_string and ")" in markdown_string):
        start_link = markdown_string.find("[")
        end_link = markdown_string.find("]")
        start_paren = markdown_string.find("(")
        end_paren = markdown_string.find(")")

        if start_link < start_paren and end_link < end_paren:
            markdown_string = markdown_string[:start_link] + markdown_string[start_paren+1:end_paren] + markdown_string[end_paren+1:]

    return markdown_string