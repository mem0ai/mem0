# Jean Memory - Your Personal Memory Layer

Jean Memory is your personal memory layer for LLMs, now available as a cloud-hosted service and for local development. It allows you to build AI applications with personalized memories while giving you options for data control.

**Live Cloud Version:**
*   **Frontend UI:** [https://jean-memory-ui.onrender.com](https://jean-memory-ui.onrender.com)
*   **Backend API:** `https://jean-memory-api.onrender.com`
    *   API Docs: [https://jean-memory-api.onrender.com/docs](https://jean-memory-api.onrender.com/docs)

To use the cloud version, simply visit the Frontend UI link above, sign up or log in, and follow the instructions to connect your MCP clients using the provided production API endpoints.

![Jean Memory](https://github.com/user-attachments/assets/3c701757-ad82-4afa-bfbe-e049c2b4320b)

## Local Development Setup

If you wish to run Jean Memory locally for development or contributions, follow these steps:

### Prerequisites (Local Development)

- Docker and Docker Compose
- Python 3.9+ (if modifying backend outside Docker)
- Node.js (if modifying frontend outside Docker)
- An OpenAI API Key (set in `openmemory/api/.env`)
- Supabase Project: For local development, you'll need to set up a free Supabase project and configure its URL and keys in:
    - `openmemory/api/.env` (for `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
    - `openmemory/ui/.env.local` (for `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- Qdrant Instance: For local development, the `docker-compose.yml` includes a Qdrant service. If you prefer to use Qdrant Cloud, configure `QDRANT_HOST` and `QDRANT_API_KEY` in `openmemory/api/.env`.

### Quickstart (Local Development)

1.  **Clone the main `mem0` repository:**
    ```bash
    git clone https://github.com/mem0ai/mem0.git
    cd mem0/openmemory
    ```

2.  **Set up Environment Variables:**
    *   In the `openmemory/api/` directory, copy `.env.example` to `.env`:
        ```bash
        cp api/.env.example api/.env
        ```
    *   Edit `api/.env` with your `OPENAI_API_KEY`, Supabase URL/service_key, and optionally Qdrant Cloud details.
    *   In the `openmemory/ui/` directory, copy `.env.example` to `.env.local` (if an example exists, otherwise create it):
        ```bash
        # cp ui/.env.example ui/.env.local (if example exists)
        # Create ui/.env.local if it doesn't exist
        ```
    *   Edit `ui/.env.local` with your `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Ensure `NEXT_PUBLIC_API_URL` is set to `http://localhost:8765` for local development.

3.  **Build and Run with Docker Compose:**
    From the `openmemory/` directory:
    ```bash
    make build # or docker compose build
    make up    # or docker compose up -d
    ```

4.  **Access Local Services:**
    *   Jean Memory API server: `http://localhost:8765` (API docs: `http://localhost:8765/docs`)
    *   Jean Memory UI: `http://localhost:3000`

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
