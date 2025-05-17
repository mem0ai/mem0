# Jean Memory

Jean Memory is your personal memory layer for LLMs - private, portable, and open-source. Your memories live locally, giving you complete control over your data. Build AI applications with personalized memories while keeping your data secure.

![Jean Memory](https://github.com/user-attachments/assets/3c701757-ad82-4afa-bfbe-e049c2b4320b)

## Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for backend development)
- Node.js (for frontend development)
- OpenAI API Key (required for LLM interactions)

## Quickstart

You can run the project using the following two commands:
```bash
make build # builds the mcp server and ui
make up  # runs jean memory mcp server and ui
```

After running these commands, you will have:
- Jean Memory MCP server running at: http://localhost:8765 (API documentation available at http://localhost:8765/docs)
- Jean Memory UI running at: http://localhost:3000

## Project Structure

- `api/` - Backend APIs + MCP server
- `ui/` - Frontend React application

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
2. Create your feature branch (`git checkout -b jean-memory/feature/amazing-feature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin jean-memory/feature/amazing-feature`)
5. Open a Pull Request

## Community

Join us in building the future of AI memory management! Your contributions help make Jean Memory better for everyone.

<a href="https://mem0.dev/jean-memory">Jean Memory</a>
