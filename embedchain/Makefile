# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip
PROJECT_NAME := embedchain

# Targets
.PHONY: install format lint clean test ci_lint ci_test coverage

install:
	poetry install

# TODO: use a more efficient way to install these packages
install_all:
	poetry install --all-extras
	poetry run pip install ruff==0.6.9 pinecone-text pinecone-client langchain-anthropic "unstructured[local-inference, all-docs]" ollama langchain_together==0.1.3 \
		langchain_cohere==0.1.5 deepgram-sdk==3.2.7 langchain-huggingface psutil clarifai==10.0.1 flask==2.3.3 twilio==8.5.0 fastapi-poe==0.0.16 discord==2.3.2 \
	 	slack-sdk==3.21.3 huggingface_hub==0.23.0 gitpython==3.1.38 yt_dlp==2023.11.14 PyGithub==1.59.1 feedparser==6.0.10 newspaper3k==0.2.8 listparser==0.19 \
	 	modal==0.56.4329 dropbox==11.36.2 boto3==1.34.20 youtube-transcript-api==0.6.1 pytube==15.0.0 beautifulsoup4==4.12.3

install_es:
	poetry install --extras elasticsearch

install_opensearch:
	poetry install --extras opensearch

install_milvus:
	poetry install --extras milvus

shell:
	poetry shell

py_shell:
	poetry run python

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

clean:
	rm -rf dist build *.egg-info

lint:
	poetry run ruff .

build:
	poetry build

publish:
	poetry publish

# for example: make test file=tests/test_factory.py
test:
	poetry run pytest $(file)

coverage:
	poetry run pytest --cov=$(PROJECT_NAME) --cov-report=xml
