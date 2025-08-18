#!/usr/bin/env python3
"""
Comprehensive AWS Bedrock Integration Examples for Mem0

This file demonstrates all the capabilities of the enhanced AWS Bedrock integration
including support for Amazon Nova models and all supported providers.
"""

import os
import sys
from typing import List, Dict, Any

# Add the mem0 package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.aws_bedrock import AWSBedrockLLM


def example_basic_nova_usage():
    """Demonstrate basic usage with Amazon Nova models."""
    print("🚀 Basic Amazon Nova Usage")
    print("=" * 50)
    
    # Configure Nova model
    config = AWSBedrockConfig(
        model="amazon.nova-3-mini-20241119-v1:0",
        temperature=0.1,
        max_tokens=1000,
        aws_region="us-west-2"
    )
    
    # Initialize LLM
    llm = AWSBedrockLLM(config)
    
    # Test basic conversation
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Hello! Can you tell me about AWS Bedrock Nova models?"}
    ]
    
    try:
        response = llm.generate_response(messages)
        print(f"✅ Nova Response: {response[:200]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


def example_nova_with_tools():
    """Demonstrate Nova models with tool calling."""
    print("🔧 Amazon Nova with Tool Calling")
    print("=" * 50)
    
    config = AWSBedrockConfig(
        model="amazon.nova-3-mini-20241119-v1:0",
        temperature=0.1,
        max_tokens=1000,
        aws_region="us-west-2"
    )
    
    llm = AWSBedrockLLM(config)
    
    # Define tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather information for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
    
    messages = [
        {"role": "user", "content": "What's the weather like in Seattle?"}
    ]
    
    try:
        response = llm.generate_response(messages, tools=tools)
        print(f"✅ Tool Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


def example_all_providers():
    """Demonstrate usage with different providers."""
    print("🌐 All Supported Providers")
    print("=" * 50)
    
    # Test different providers
    providers_to_test = [
        ("amazon", "amazon.nova-3-mini-20241119-v1:0"),
        ("anthropic", "anthropic.claude-3-5-sonnet-20240620-v1:0"),
        ("meta", "meta.llama-3-70b-instruct-v1:0"),
        ("mistral", "mistral.mistral-7b-instruct-v0:2"),
        ("cohere", "cohere.command-r-plus-v1:0"),
        ("ai21", "ai21.j2-ultra-v1"),
    ]
    
    for provider_name, model_id in providers_to_test:
        print(f"Testing {provider_name.upper()} provider...")
        
        try:
            config = AWSBedrockConfig(
                model=model_id,
                temperature=0.1,
                max_tokens=500,
                aws_region="us-west-2"
            )
            
            llm = AWSBedrockLLM(config)
            
            # Get capabilities
            capabilities = llm.get_model_capabilities()
            print(f"  ✅ Capabilities: {capabilities}")
            
            # Test basic response
            messages = [{"role": "user", "content": "Say hello!"}]
            response = llm.generate_response(messages)
            print(f"  ✅ Response: {response[:100]}...")
            
        except Exception as e:
            print(f"  ❌ Error with {provider_name}: {e}")
        
        print()


def example_model_discovery():
    """Demonstrate model discovery capabilities."""
    print("🔍 Model Discovery")
    print("=" * 50)
    
    config = AWSBedrockConfig(aws_region="us-west-2")
    llm = AWSBedrockLLM(config)
    
    try:
        # List all available models
        models = llm.list_available_models()
        print(f"Found {len(models)} models in the region")
        
        # Group by provider
        providers = {}
        for model in models:
            provider = model["provider"]
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model["model_name"])
        
        # Display summary
        for provider, model_names in providers.items():
            print(f"\n{provider.upper()}: {len(model_names)} models")
            for name in model_names[:3]:  # Show first 3
                print(f"  - {name}")
            if len(model_names) > 3:
                print(f"  ... and {len(model_names) - 3} more")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


def example_advanced_configuration():
    """Demonstrate advanced configuration options."""
    print("⚙️ Advanced Configuration")
    print("=" * 50)
    
    # Test different configurations
    configs = [
        {
            "name": "High Creativity",
            "config": AWSBedrockConfig(
                model="amazon.nova-3-mini-20241119-v1:0",
                temperature=0.9,
                top_p=0.95,
                max_tokens=2000
            )
        },
        {
            "name": "Focused Response",
            "config": AWSBedrockConfig(
                model="amazon.nova-3-mini-20241119-v1:0",
                temperature=0.1,
                top_p=0.8,
                max_tokens=500
            )
        },
        {
            "name": "Balanced",
            "config": AWSBedrockConfig(
                model="amazon.nova-3-mini-20241119-v1:0",
                temperature=0.5,
                top_p=0.9,
                max_tokens=1000
            )
        }
    ]
    
    for config_info in configs:
        print(f"Testing {config_info['name']} configuration...")
        
        try:
            llm = AWSBedrockLLM(config_info["config"])
            
            messages = [{"role": "user", "content": "Write a short creative story about a robot."}]
            response = llm.generate_response(messages)
            
            print(f"  ✅ Response: {response[:150]}...")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()


def example_error_handling():
    """Demonstrate error handling and validation."""
    print("🚨 Error Handling and Validation")
    print("=" * 50)
    
    # Test invalid model
    try:
        config = AWSBedrockConfig(model="invalid.model")
        llm = AWSBedrockLLM(config)
        print("❌ Should have failed with invalid model")
    except ValueError as e:
        print(f"✅ Correctly caught invalid model: {e}")
    
    # Test invalid region
    try:
        config = AWSBedrockConfig(
            model="amazon.nova-3-mini-20241119-v1:0",
            aws_region="invalid-region"
        )
        llm = AWSBedrockLLM(config)
        print("❌ Should have failed with invalid region")
    except Exception as e:
        print(f"✅ Correctly caught invalid region: {e}")
    
    # Test model validation
    config = AWSBedrockConfig(model="amazon.nova-3-mini-20241119-v1:0")
    is_valid = config.validate_model_format()
    print(f"✅ Model format validation: {is_valid}")
    
    # Test capabilities
    capabilities = config.get_model_capabilities()
    print(f"✅ Model capabilities: {capabilities}")
    
    print()


def example_streaming_support():
    """Demonstrate streaming capabilities."""
    print("🌊 Streaming Support")
    print("=" * 50)
    
    config = AWSBedrockConfig(
        model="amazon.nova-3-mini-20241119-v1:0",
        temperature=0.1,
        max_tokens=1000,
        aws_region="us-west-2"
    )
    
    llm = AWSBedrockLLM(config)
    
    # Check if streaming is supported
    capabilities = llm.get_model_capabilities()
    if capabilities["supports_streaming"]:
        print("✅ This model supports streaming")
        
        messages = [{"role": "user", "content": "Write a short poem about AI."}]
        
        try:
            # Note: Actual streaming implementation would be here
            response = llm.generate_response(messages, stream=True)
            print(f"✅ Streaming response: {response[:100]}...")
        except Exception as e:
            print(f"❌ Streaming error: {e}")
    else:
        print("❌ This model doesn't support streaming")
    
    print()


def main():
    """Run all examples."""
    print("🚀 AWS Bedrock Comprehensive Examples")
    print("=" * 60)
    print()
    
    # Check if AWS credentials are available
    if not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
        print("⚠️  AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("   or configure AWS_PROFILE before running these examples.")
        print()
        print("Examples will show configuration but may fail on actual API calls.")
        print()
    
    try:
        example_basic_nova_usage()
        example_nova_with_tools()
        example_all_providers()
        example_model_discovery()
        example_advanced_configuration()
        example_error_handling()
        example_streaming_support()
        
        print("🎉 All examples completed!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Examples interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")


if __name__ == "__main__":
    main()
