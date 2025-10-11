#!/usr/bin/env python3
"""
Example demonstrating how to use AWS Bedrock reranker with Mem0.

This example shows how to configure and use the AWS Bedrock reranker
with Cohere's rerank-v3-5 model for improved search relevance.
"""

import os
from mem0 import Memory


def main():
    """Main example function."""
    
    # Configuration for AWS Bedrock reranker
    config = {
        # Basic Mem0 configuration
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "mem0_example",
                "path": "./qdrant_db"
            }
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY")
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": os.getenv("OPENAI_API_KEY")
            }
        },
        
        # AWS Bedrock reranker configuration
        "reranker": {
            "provider": "aws_bedrock",
            "config": {
                "model": "cohere.rerank-v3-5:0",
                "region": "us-west-2",
                # Optional: AWS credentials (if not using default credential chain)
                # "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                # "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "top_n": 5
            }
        }
    }
    
    # Initialize Memory with reranker
    print("Initializing Memory with AWS Bedrock reranker...")
    m = Memory.from_config(config)
    
    # Add some sample memories
    print("Adding sample memories...")
    memories_to_add = [
        "I love Python programming and machine learning",
        "I work as a software engineer at a tech company",
        "I enjoy hiking and outdoor activities on weekends",
        "I'm interested in artificial intelligence and neural networks",
        "I live in San Francisco and love the tech scene",
        "I'm learning about cloud computing and AWS services",
        "I have a dog named Max who loves to play fetch",
        "I prefer working remotely and using agile methodologies"
    ]
    
    for memory in memories_to_add:
        m.add(memory, user_id="example_user")
    
    print(f"Added {len(memories_to_add)} memories")
    
    # Test search without reranker (for comparison)
    print("\n" + "="*50)
    print("SEARCH RESULTS WITH RERANKER:")
    print("="*50)
    
    search_queries = [
        "What do I know about programming?",
        "Tell me about my work preferences",
        "What are my hobbies and interests?"
    ]
    
    for query in search_queries:
        print(f"\nQuery: '{query}'")
        results = m.search(query, user_id="example_user", limit=3)
        
        print("Top results:")
        for i, result in enumerate(results["results"], 1):
            print(f"  {i}. {result['memory']} (score: {result['score']:.3f})")
    
    print("\n" + "="*50)
    print("Example completed successfully!")
    print("="*50)
    print("\nTo run this example:")
    print("1. Set your AWS credentials (via AWS CLI, environment variables, or IAM roles)")
    print("2. Set OPENAI_API_KEY environment variable")
    print("3. Install required dependencies: pip install mem0ai boto3")
    print("4. Run: python aws_bedrock_reranker_example.py")


if __name__ == "__main__":
    main()

