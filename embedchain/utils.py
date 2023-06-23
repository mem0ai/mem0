import re


def clean_string(text):
    text = text.replace('\n', ' ')
    cleaned_text = re.sub(r'\s+', ' ', text.strip())
    cleaned_text = cleaned_text.replace('\\', '')
    cleaned_text = cleaned_text.replace('#', ' ')
    cleaned_text = re.sub(r'([^\w\s])\1*', r'\1', cleaned_text)
    return cleaned_text
