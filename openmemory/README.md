# OpenMemory

OpenMemory is your personal memory layer for LLMs - private, portable, and open-source. Your memories live locally, giving you complete control over your data. Build AI applications with personalized memories while keeping your data secure.

![OpenMemory](https://github.com/user-attachments/assets/3c701757-ad82-4afa-bfbe-e049c2b4320b)

## Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for backend development)
- Node.js (for frontend development)
- OpenAI API Key (required for LLM interactions)

## Quickstart

You can run the project using the following two commands:
```bash
make build # builds the mcp server
make up  # runs openmemory mcp server
make ui   # runs openmemory ui
```

## Project Structure

- `api/` - Backend APIs + MCP server
- `ui/` - Frontend React application

## Getting Started

### Backend Setup

The backend runs in Docker containers. To start the backend:

```bash
# Copy environment file and edit file to update OPENAI_API_KEY and other secrets
make env

# Build the containers
make build

# Start the services
make up
```

Other useful backend commands:
```bash
# Run database migrations
make migrate

# View logs
make logs

# Open a shell in the API container
make shell

# Run tests
make test

# Stop the services
make down
```

### Frontend Setup

The frontend is a React application. To start the frontend:

```bash
# Install dependencies and start the production server
make ui
```

Next, OpenMemory dashboard will be available at `http://localhost:3000` which will guide you through installing MCP server in your MCP clients.

## Development

- Backend API runs at `http://localhost:8765`
- Frontend runs at `http://localhost:3000`
- API documentation is available at `http://localhost:8765/docs`

## Contributing

We are a team of developers passionate about the future of AI and open-source software. With years of experience in both fields, we believe in the power of community-driven development and are excited to build tools that make AI more accessible and personalized.

We welcome all forms of contributions:
- Bug reports and feature requests
- Documentation improvements
- Code contributions
- Testing and feedback
- Community support

How to contribute:

1. Fork the repository
2. Create your feature branch (`git checkout -b openmemory/feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin openmemory/feature/amazing-feature`)
5. Open a Pull Request

We value:
- Clean, well-documented code
- Thoughtful discussions about features and improvements
- Respectful and constructive feedback
- A welcoming environment for all contributors

Join us in building the future of AI memory management! Your contributions help make OpenMemory better for everyone.

## Roadmap
- Add support for other LLM providers
- Support different user ids
- Set retention period for memories

