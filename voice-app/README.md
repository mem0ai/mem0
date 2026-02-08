# AI Voice Assistant with Memory

A real-time voice application featuring an animated 3D orb, persistent conversation memory via mem0, and integration with Claude AI through the Model Context Protocol (MCP).

## Features

- **Real-time Voice Interaction**: Speech-to-text (Whisper) → AI processing (Claude) → Text-to-speech (Eleven Labs)
- **Animated 3D Orb**: Beautiful particle effects that change color based on who's speaking:
  - Blue smoke when user is speaking
  - Pink smoke when AI is responding
  - Smooth rotating 3D sphere with WebGL
- **Chat Interface**: Real-time transcription displayed in speech bubbles
- **Persistent Memory**: Conversation context stored and retrieved using mem0
- **Web Search**: Tavily integration for current information
- **MCP Integration**: Modular tool system for extensibility

## Architecture

```
Frontend (Next.js + Three.js)
    ↕ WebSocket
Backend (Node.js + TypeScript)
    ↕ MCP Protocol
MCP Servers (mem0, Tavily, etc.)
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system design.

## Prerequisites

- Node.js 20+
- npm or yarn
- API Keys:
  - [Anthropic API Key](https://console.anthropic.com/) (Claude)
  - [OpenAI API Key](https://platform.openai.com/) (Whisper)
  - [Eleven Labs API Key](https://elevenlabs.io/)
  - [mem0 API Key](https://app.mem0.ai/)
  - [Tavily API Key](https://tavily.com/) (optional)

## Quick Start

### 1. Clone and Install

```bash
cd voice-app

# Install backend dependencies
cd backend
npm install

# Install frontend dependencies
cd ../frontend
npm install
```

### 2. Configure Environment Variables

**Backend (.env)**

Create `backend/.env` from the template:

```bash
cd backend
cp ../.env.example .env
```

Edit `.env` and add your API keys:

```bash
ANTHROPIC_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
MEM0_API_KEY=m0-7Unb8KnmI8jwmtNwkVWhvraySvNYne8Z3WDfnWKd
TAVILY_API_KEY=your_tavily_api_key

# mem0 Configuration (pre-configured)
MEM0_ORG=daddyholmes-default-org
MEM0_USER_ID=mem0-zai-crew

# Server Configuration
PORT=3001
WS_PORT=8080
NODE_ENV=development
```

**Frontend (.env.local)**

Create `frontend/.env.local`:

```bash
cd ../frontend
cp .env.local.example .env.local
```

The default WebSocket URL should work for local development:

```bash
NEXT_PUBLIC_WS_URL=ws://localhost:8080
```

### 3. Start the Application

**Terminal 1 - Backend:**

```bash
cd backend
npm run dev
```

You should see:
```
HTTP server listening on port 3001
WebSocket server listening on port 8080
Voice application backend started successfully
```

**Terminal 2 - Frontend:**

```bash
cd frontend
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000)

### 4. Use the Voice Assistant

1. **Grant microphone permissions** when prompted
2. **Hold the microphone button** to speak
3. **Release** to send your message
4. The **orb turns blue** while you speak
5. The **orb turns pink** while AI responds
6. See **transcriptions** appear in real-time in the chat

## Project Structure

```
voice-app/
├── backend/                    # Node.js backend
│   ├── src/
│   │   ├── index.ts           # Entry point
│   │   ├── websocket/         # WebSocket server & handlers
│   │   ├── voice/             # STT, TTS, pipeline
│   │   ├── mcp/               # MCP client & server configs
│   │   ├── llm/               # Claude integration
│   │   ├── types/             # TypeScript types
│   │   └── utils/             # Utilities (logger, etc.)
│   ├── package.json
│   └── tsconfig.json
│
├── frontend/                   # Next.js frontend
│   ├── app/                   # Next.js app router
│   ├── components/            # React components
│   │   ├── AnimatedOrb.tsx    # 3D orb with particles
│   │   ├── ChatBubble.tsx     # Message bubble
│   │   ├── ChatUI.tsx         # Chat interface
│   │   └── VoiceAssistant.tsx # Main component
│   ├── hooks/                 # Custom React hooks
│   │   ├── useWebSocket.ts    # WS connection
│   │   └── useAudio.ts        # Audio recording/playback
│   ├── lib/                   # Utilities
│   └── package.json
│
├── .env.example               # Environment template
├── ARCHITECTURE.md            # Architecture documentation
└── README.md                  # This file
```

## How It Works

### Voice Pipeline

1. **User speaks** → Frontend captures audio via `getUserMedia()`
2. **Audio chunks** → Sent to backend via WebSocket
3. **Speech-to-Text** → OpenAI Whisper transcribes audio
4. **AI Processing** → Claude processes with MCP tools:
   - Searches mem0 for relevant conversation history
   - Can search web via Tavily if needed
   - Generates natural response
5. **Text-to-Speech** → Eleven Labs synthesizes voice
6. **Audio playback** → Frontend plays audio in real-time

### Memory Integration

The application uses mem0 to:
- Store conversation history automatically
- Retrieve relevant context for each query
- Provide personalized responses based on past interactions

User ID: `mem0-zai-crew`
Organization: `daddyholmes-default-org`

### MCP Tools Available

**mem0 Server:**
- `add-memory`: Store conversation context
- `search-memories`: Retrieve relevant memories
- `get-all-memories`: Get complete memory history

**Tavily Server:**
- `search`: Web search queries
- `extract`: Extract content from URLs

## Development

### Backend Development

```bash
cd backend

# Development with hot reload
npm run dev

# Type checking
npm run type-check

# Build for production
npm run build

# Start production server
npm start
```

### Frontend Development

```bash
cd frontend

# Development server
npm run dev

# Type checking
npm run type-check

# Build for production
npm run build

# Start production server
npm start
```

## Customization

### Change Voice

Edit `backend/.env`:

```bash
# Available voices at: https://elevenlabs.io/voice-library
ELEVENLABS_VOICE_ID=your_preferred_voice_id
```

### Change AI Model

Edit `backend/.env`:

```bash
# Available models: claude-sonnet-4-5-20250929, claude-opus-4-20250514
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

### Modify Orb Colors

Edit `frontend/components/AnimatedOrb.tsx`:

```typescript
// User speaking color (currently blue #4A90E2)
colors[i] = 0.29;
colors[i + 1] = 0.56;
colors[i + 2] = 0.89;

// AI speaking color (currently pink #E24A90)
colors[i] = 0.89;
colors[i + 1] = 0.29;
colors[i + 2] = 0.56;
```

### Add More MCP Servers

Edit `backend/src/mcp/servers.ts`:

```typescript
export const mcpServers: Record<string, MCPServerConfig> = {
  // ... existing servers
  myNewServer: {
    name: 'myNewServer',
    command: 'npx',
    args: ['-y', '@my-org/mcp-server'],
    env: {
      API_KEY: process.env.MY_SERVER_API_KEY || '',
    },
  },
};
```

## Troubleshooting

### WebSocket Connection Failed

- Check that backend is running on port 8080
- Verify `NEXT_PUBLIC_WS_URL` in frontend `.env.local`
- Check firewall settings

### No Audio Playback

- Grant microphone permissions in browser
- Check browser console for audio context errors
- Ensure HTTPS (required for microphone access in production)

### MCP Tools Not Working

- Verify API keys in backend `.env`
- Check backend logs for MCP connection errors
- Ensure npx can download and run MCP servers

### Poor Voice Quality

- Check internet connection
- Increase `ELEVENLABS_MODEL_ID` to a higher quality model
- Adjust voice settings in `backend/src/voice/tts.ts`

## Production Deployment

### Environment Variables

For production, set all required environment variables:

```bash
# Backend
ANTHROPIC_API_KEY=sk-...
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
MEM0_API_KEY=m0-...
TAVILY_API_KEY=tvly-...

NODE_ENV=production

# Frontend
NEXT_PUBLIC_WS_URL=wss://your-domain.com
```

### Build and Deploy

```bash
# Build backend
cd backend
npm run build

# Build frontend
cd ../frontend
npm run build

# Deploy with your preferred hosting service
# (Vercel, Railway, Render, etc.)
```

### Security Considerations

- Use HTTPS/WSS in production
- Implement authentication for WebSocket connections
- Add rate limiting to prevent API abuse
- Validate all user inputs
- Use environment variables for all secrets
- Enable CORS only for trusted origins

## License

MIT

## Credits

- **Voice Providers**: OpenAI (Whisper), Eleven Labs
- **AI**: Anthropic Claude
- **Memory**: mem0
- **Search**: Tavily
- **3D Graphics**: Three.js, React Three Fiber
- **Framework**: Next.js, Node.js

## Support

For issues and questions:
- Check the [ARCHITECTURE.md](./ARCHITECTURE.md) documentation
- Review backend logs in the terminal
- Check browser console for frontend errors
- Verify all API keys are valid and have sufficient credits

## Future Enhancements

- Multi-language support
- Voice cloning for personalized voices
- Screen sharing integration
- Mobile app (React Native)
- Offline mode with local STT/TTS
- Group conversations
- Custom wake word detection
