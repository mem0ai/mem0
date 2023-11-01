# API Server Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [Setup](#setup)
3. [Usage Instructions](#usage-instructions)
4. [Curl Call Formats](#curl-call-formats)
5. [Setting Your OpenAI Key](#setting-your-openai-key)


## Introduction

The API server example provided here is a Flask-based server that integrates the Embedchain package. It offers endpoints to add, query, and chat with a chatbot using JSON requests.

## Setup

### Docker Setup

1. Open the `variables.env` file and add your OpenAI API key.

2. To set up your API server using Docker, run the following command in this folder using your terminal:

   ```bash
   docker-compose up --build
   ```

## Usage Instructions
Your API server is now running on http://localhost:5000/. To use the API server, make an API call to the following endpoints:

### '/add' - Add Data Sources

Request:
{
  "data_type": "your_data_type_here",
  "url_or_text": "your_url_or_text_here"
}

Response:
{
  "data": "Added data_type: url_or_text"
}

### /query - Ask Queries

Request:
{
  "question": "your_question_here"
}

Response:
{
  "data": "your_answer_here"
}


## Curl Call Formats

Here are the curl call formats to interact with the API server:

### Adding Data Sources (/add):

curl -X POST \
     -H "Content-Type: application/json" \
     -d '{
         "data_type": "your_data_type_here",
         "url_or_text": "your_url_or_text_here"
     }' \
     http://localhost:5000/add

### Asking Queries (/query):

curl -X POST \
     -H "Content-Type: application/json" \
     -d '{
         "question": "your_question_here"
     }' \
     http://localhost:5000/query


## Setting Your OpenAI Key

To set your OpenAI API key, you should add it to the variables.env file. This key is necessary to interact with the API server effectively.