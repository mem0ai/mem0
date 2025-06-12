import click
import subprocess
import os
import pytest

@click.group()
def cli():
    """
    Jean Memory CLI
    
    A command-line interface for managing and testing the Jean Memory Agent API.
    """
    pass

@cli.command()
@click.option('--test-file', default='examples/test_jean_memory_api.py', help='Path to the pytest file.')
@click.option('-k', '--keyword', default=None, help='Pytest keyword expression to select specific tests (e.g., "basic" or "not llm").')
def test(test_file, keyword):
    """
    Run the Jean Memory API test suite using pytest.
    
    This requires two environment variables to be set:
    - JEAN_API_TOKEN: Your authentication token for the Jean Memory API.
    - OPENAI_API_KEY: Your key for OpenAI to run LLM-based tests.
    """
    click.echo(f"🚀 Running Jean Memory Tests from: {test_file} 🚀")
    
    # Check for required environment variables
    if not os.environ.get("JEAN_API_TOKEN") and not os.environ.get("USER_ID"):
        click.echo(click.style("ERROR: JEAN_API_TOKEN is not set. Please set it to run tests.", fg='red'))
        click.echo(click.style("(For local tests, setting USER_ID is an alternative.)", fg='yellow'))
        return
    if not os.environ.get("OPENAI_API_KEY"):
        click.echo(click.style("Warning: OPENAI_API_KEY is not set. LLM-dependent tests will be skipped.", fg='yellow'))
    
    # Base pytest command
    command = ["pytest", "-v", test_file]
    
    # Add keyword filter if provided
    if keyword:
        command.extend(["-k", keyword])
        click.echo(f"   Filtering tests with keyword: {keyword}")

    try:
        # We set the USER_ID here to ensure local tests run correctly, if it's not already set
        env = os.environ.copy()
        if "USER_ID" not in env:
            env["USER_ID"] = "local_test_user_cli" # Default for CLI runs
        
        subprocess.run(command, check=True, env=env)
        click.echo(click.style("\\n✅ All selected tests passed successfully.", fg='green'))
    except subprocess.CalledProcessError:
        click.echo(click.style("\\n❌ Some tests failed.", fg='red'))

if __name__ == '__main__':
    cli() 