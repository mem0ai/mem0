# OpenMemory Tests

This directory contains various tests for the OpenMemory application.

## Test Files

- `test-production-compatibility.py` - Validates that local development setup doesn't break production deployment
- `test-local-setup.py` - Tests the local development environment setup
- `test_mcp.py` - Tests for MCP (Model Context Protocol) functionality

## Running Tests

### Production Compatibility Test
```bash
python tests/test-production-compatibility.py
```

### Local Setup Test
```bash
python tests/test-local-setup.py
```

### MCP Test
```bash
python tests/test_mcp.py
```

## Test Categories

- **Compatibility Tests**: Ensure local and production environments work correctly
- **Setup Tests**: Validate development environment configuration
- **Integration Tests**: Test external service integrations (MCP, etc.) 