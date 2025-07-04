#!/bin/bash
set -e

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null
then
    echo "Python 3 is not installed. Please install Python 3 from python.org or via your system's package manager."
    exit 1
fi

# Check if pip (for Python 3) is installed
if ! python3 -m pip --version &> /dev/null
then
    echo "pip for Python 3 is not installed. It usually comes with Python 3. You can try to install it via 'python3 -m ensurepip --upgrade' or your system's package manager."
    exit 1
fi

# Check if Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "Poetry is not installed. Please install Poetry using the official recommended method: 'curl -sSL https://install.python-poetry.org | python3 -'"
    echo "After installing Poetry, please re-run this script: ./install_mem0.sh"
    exit 1
fi

echo "All prerequisite dependencies (Python 3, pip, Poetry) are installed."

# Install base dependencies using Poetry
echo "Installing base dependencies with Poetry..."
if ! poetry install; then
    echo "Poetry install failed. Please check the output above for errors."
    exit 1
fi

echo "Base dependencies installed successfully."

# Install additional dependencies using pip
echo "Installing additional dependencies with pip..."
if ! python3 -m pip install ruff==0.6.9 groq together boto3 litellm ollama chromadb weaviate weaviate-client sentence_transformers vertexai google-generativeai elasticsearch opensearch-py vecs pinecone pinecone-text faiss-cpu langchain-community upstash-vector azure-search-documents langchain-memgraph; then
    echo "Pip install of additional dependencies failed. Please check the output above for errors."
    exit 1
fi

echo "Additional dependencies installed successfully."

# Final success message
echo "Mem0 installation complete! All dependencies have been installed."
