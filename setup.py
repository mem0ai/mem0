import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="embedchain",
    version="0.0.30",
    author="Taranjeet Singh",
    author_email="reachtotj@gmail.com",
    description="embedchain is a framework to easily create LLM powered bots over any dataset",  # noqa:E501
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/embedchain/embedchain",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    py_modules=["embedchain"],
    install_requires=[
        "langchain>=0.0.205",
        "requests",
        "openai",
        "chromadb>=0.4.2",
        "youtube-transcript-api",
        "beautifulsoup4",
        "pypdf",
        "pytube",
        "lxml",
        "gpt4all",
        "sentence_transformers",
        "docx2txt",
        "pydantic==1.10.8",
        "replicate==0.9.0",
        "duckduckgo-search==3.8.4",
    ],
    extras_require={"dev": ["black", "ruff", "isort", "pytest"]},
)
