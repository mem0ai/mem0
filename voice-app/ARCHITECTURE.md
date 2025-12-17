# Voice Application Architecture

## Overview
A real-time voice application with animated UI, MCP integration, and persistent memory capabilities using mem0.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React/Next.js)                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Animated Orb (Three.js + React Three Fiber)             │  │
│  │  - Blue smoke particles (user speaking)                  │  │
│  │  - Pink smoke particles (AI speaking)                    │  │
│  │  - Rotating 3D orb centerpiece                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Chat UI                                                 │  │
│  │  - Speech bubbles with real-time transcriptions          │  │
│  │  - User messages (left-aligned)                          │  │
│  │  - AI responses (right-aligned)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  WebSocket Client                                        │  │
│  │  - Audio streaming (bidirectional)                       │  │
│  │  - Real-time transcription updates                       │  │
│  │  - Status events (speaking/listening states)             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↕ WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (Node.js/TypeScript)                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  WebSocket Server (ws library)                           │  │
│  │  - Audio chunk handling                                  │  │
│  │  - Session management                                    │  │
│  │  - Event broadcasting                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Voice Pipeline Orchestrator                             │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────┐ │  │
│  │  │  STT Engine    │→ │  LLM + MCP     │→ │ TTS Engine │ │  │
│  │  │  (Whisper or   │  │  (Claude with  │  │ (Eleven    │ │  │
│  │  │   Realtime API)│  │   MCP tools)   │  │  Labs)     │ │  │
│  │  └────────────────┘  └────────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP Client Manager                                      │  │
│  │  - Claude SDK integration                                │  │
│  │  - MCP server connections                                │  │
│  │  - Tool execution routing                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↕ MCP Protocol
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Servers Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  mem0 MCP    │  │  Tavily MCP  │  │  Code Execution MCP  │ │
│  │              │  │              │  │                      │ │
│  │  - add()     │  │  - search()  │  │  - execute_code()    │ │
│  │  - search()  │  │  - crawl()   │  │  - sandbox_env()     │ │
│  │  - get_all() │  │              │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Frontend (React/Next.js)

#### Animated Orb Component
- **Library**: React Three Fiber + Three.js
- **Features**:
  - 3D sphere with gradient materials
  - Particle system for smoke effects (using PointsMaterial)
  - Blue particles: `color: #4A90E2`, emit when `userSpeaking === true`
  - Pink particles: `color: #E24A90`, emit when `aiSpeaking === true`
  - Rotation animation: continuous slow rotation on Y-axis
  - Glow effect using bloom post-processing

#### Chat UI Component
- **Layout**: Vertical scrollable list of messages
- **Message Bubbles**:
  - User: Left-aligned, blue background (#E3F2FD)
  - AI: Right-aligned, pink background (#FCE4EC)
  - Animated appearance with fade-in effect
  - Real-time transcription updates (streaming text)

#### WebSocket Client
- **Library**: native WebSocket API
- **Events**:
  - `audio_chunk`: Send user audio to server
  - `transcription_update`: Receive real-time STT updates
  - `ai_response`: Receive AI text response
  - `audio_response`: Receive TTS audio chunks
  - `status_change`: Speaking/listening state changes

### 2. Backend (Node.js/TypeScript)

#### WebSocket Server
- **Library**: `ws` (WebSocket library)
- **Features**:
  - Session-based connections (one session per user)
  - Audio chunk buffering and streaming
  - Event-driven architecture
  - Error handling and reconnection logic

#### Voice Pipeline

**Option A: OpenAI Realtime API (Recommended for simplicity)**
- Single WebSocket connection handles both STT and TTS
- GPT-4o processes audio natively
- MCP tools injected via function calling
- Pros: Lowest latency, native audio understanding
- Cons: Limited to OpenAI models, no Claude integration

**Option B: Modular Pipeline (Recommended for flexibility)**
- STT: OpenAI Whisper API (or Deepgram for streaming)
- LLM: Claude 4.5 Sonnet with MCP tools
- TTS: Eleven Labs for high-quality voice
- Pros: Best-in-class for each component, Claude MCP support
- Cons: Higher latency due to multiple API calls

**Selected Approach**: Option B - Modular Pipeline
- Allows use of Claude with MCP
- Better voice quality with Eleven Labs
- More control over each stage
- Can optimize with streaming/caching

#### MCP Integration

**MCP Client Configuration**:
```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// Configure MCP servers
const mcpServers = {
  mem0: {
    command: "npx",
    args: ["-y", "@mem0/mcp-server"],
    env: {
      MEM0_API_KEY: process.env.MEM0_API_KEY,
      DEFAULT_USER_ID: "mem0-zai-crew",
    },
  },
  tavily: {
    command: "npx",
    args: ["-y", "@tavily/mcp-server"],
    env: {
      TAVILY_API_KEY: process.env.TAVILY_API_KEY,
    },
  },
};
```

**Code Execution Pattern** (from Anthropic blog):
Instead of direct tool calls, Claude writes code that calls MCP tools:
```python
# Instead of calling search_memory tool directly
# Claude writes and executes:
from mem0 import MemoryClient
memory = MemoryClient()
results = memory.search("user preferences", user_id="mem0-zai-crew")
print(results)
```

### 3. MCP Servers

#### mem0 MCP Server
- **Package**: `@mem0/mcp-server`
- **Configuration**:
  - API Key: `m0-7Unb8KnmI8jwmtNwkVWhvraySvNYne8Z3WDfnWKd`
  - Organization: `daddyholmes-default-org`
  - User ID: `mem0-zai-crew`
- **Tools**:
  - `add`: Store conversation context
  - `search`: Retrieve relevant memories
  - `get_all`: Get user's memory history

#### Tavily MCP Server
- **URL**: `https://tavily.api.tadata.com/mcp/tavily/bout-equable-vanity-77266y`
- **Tools**:
  - `search`: Web search queries
  - `extract`: Extract content from URLs

#### Code Execution MCP
- **Custom server** for executing Python/JavaScript code
- Sandboxed environment using Docker or VM
- Tools:
  - `execute_code`: Run code snippets
  - `install_package`: Install dependencies

## Voice Provider Integration

### Eleven Labs (Primary TTS)
- **API**: Eleven Labs TTS API
- **Voice ID**: Will be configurable
- **Features**:
  - Streaming audio generation
  - Multiple voices and languages
  - Emotion control
  - Low latency mode

### OpenAI Whisper (STT)
- **API**: OpenAI Audio API
- **Model**: `whisper-1`
- **Features**:
  - High accuracy transcription
  - Multi-language support
  - Automatic language detection

### Qwen (Alternative)
- **Model**: Qwen2.5-Omni or Qwen3-Omni
- **Protocol**: WebSocket
- **Use Case**: Fallback or multi-provider support
- **Features**:
  - Multimodal understanding
  - Real-time streaming
  - Built-in VAD

## Data Flow

### User Speaks → AI Responds

1. **User speaks into microphone**
   - Frontend captures audio via `navigator.mediaDevices.getUserMedia()`
   - Audio chunks sent to backend via WebSocket

2. **Speech-to-Text**
   - Backend buffers audio chunks
   - Sends to Whisper API when silence detected (VAD)
   - Receives transcription text

3. **LLM Processing with MCP**
   - Transcription sent to Claude API
   - Claude decides which MCP tools to use:
     - Search memories (mem0)
     - Search web (Tavily)
     - Execute code if needed
   - Claude generates response text

4. **Text-to-Speech**
   - Response text sent to Eleven Labs
   - Streaming audio chunks received
   - Audio sent to frontend via WebSocket

5. **Frontend Playback**
   - Audio chunks played in real-time
   - Pink smoke particles activated
   - Speech bubble with AI response displayed

## Technology Stack

### Frontend
- **Framework**: Next.js 14 (App Router)
- **UI Library**: React 18
- **3D Graphics**: Three.js + React Three Fiber
- **Particle Effects**: @react-three/drei (for helpers)
- **Styling**: Tailwind CSS
- **Audio**: Web Audio API
- **State Management**: Zustand or React Context

### Backend
- **Runtime**: Node.js 20+
- **Language**: TypeScript 5+
- **WebSocket**: `ws` library
- **HTTP Server**: Express.js
- **MCP Client**: `@anthropic-ai/sdk` with MCP support
- **Audio Processing**: `@ffmpeg/ffmpeg` for format conversion

### APIs & Services
- **LLM**: Claude 4.5 Sonnet (Anthropic)
- **STT**: OpenAI Whisper API
- **TTS**: Eleven Labs API
- **Memory**: mem0 Enterprise Cloud
- **Search**: Tavily API
- **MCP Servers**: NPX-based servers

## Environment Variables

```bash
# API Keys
ANTHROPIC_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
MEM0_API_KEY=m0-7Unb8KnmI8jwmtNwkVWhvraySvNYne8Z3WDfnWKd
TAVILY_API_KEY=your_tavily_api_key

# mem0 Configuration
MEM0_ORG=daddyholmes-default-org
MEM0_USER_ID=mem0-zai-crew

# Server Configuration
PORT=3001
WS_PORT=8080
NODE_ENV=development
```

## File Structure

```
voice-app/
├── frontend/                   # Next.js frontend
│   ├── app/
│   │   ├── page.tsx           # Main chat page
│   │   ├── layout.tsx         # Root layout
│   │   └── api/               # API routes (optional)
│   ├── components/
│   │   ├── AnimatedOrb.tsx    # 3D orb with particles
│   │   ├── ChatBubble.tsx     # Message bubble component
│   │   ├── ChatUI.tsx         # Main chat interface
│   │   └── WebSocketClient.tsx # WS connection handler
│   ├── hooks/
│   │   ├── useAudio.ts        # Audio capture/playback
│   │   └── useWebSocket.ts    # WebSocket management
│   ├── lib/
│   │   └── audio-utils.ts     # Audio processing utilities
│   ├── public/
│   └── package.json
│
├── backend/                    # Node.js backend
│   ├── src/
│   │   ├── index.ts           # Server entry point
│   │   ├── websocket/
│   │   │   ├── server.ts      # WebSocket server setup
│   │   │   └── handlers.ts    # Event handlers
│   │   ├── voice/
│   │   │   ├── pipeline.ts    # Voice pipeline orchestrator
│   │   │   ├── stt.ts         # Speech-to-text (Whisper)
│   │   │   ├── tts.ts         # Text-to-speech (Eleven Labs)
│   │   │   └── vad.ts         # Voice activity detection
│   │   ├── mcp/
│   │   │   ├── client.ts      # MCP client manager
│   │   │   ├── servers.ts     # MCP server configs
│   │   │   └── tools.ts       # Tool execution logic
│   │   ├── llm/
│   │   │   └── claude.ts      # Claude API integration
│   │   └── utils/
│   │       ├── audio.ts       # Audio utilities
│   │       └── logger.ts      # Logging setup
│   ├── package.json
│   └── tsconfig.json
│
├── mcp-servers/                # Custom MCP servers
│   └── code-execution/
│       ├── index.ts
│       └── sandbox.ts
│
├── .env.example                # Environment template
├── docker-compose.yml          # Development environment
└── ARCHITECTURE.md            # This file
```

## Development Phases

### Phase 1: Core Infrastructure ✓
1. Set up project structure
2. Configure environment variables
3. Initialize frontend (Next.js) and backend (Node.js)
4. Set up WebSocket connection

### Phase 2: Basic Voice Pipeline
1. Implement audio capture in frontend
2. Set up Whisper STT integration
3. Integrate Eleven Labs TTS
4. Basic text transcription display

### Phase 3: MCP Integration
1. Configure mem0 MCP server
2. Configure Tavily MCP server
3. Integrate Claude with MCP client
4. Implement code execution pattern

### Phase 4: Animated UI
1. Create 3D orb with Three.js
2. Implement particle system
3. Add smoke color logic (blue/pink)
4. Smooth animations and transitions

### Phase 5: Chat UI
1. Design speech bubble components
2. Real-time transcription streaming
3. Message history display
4. Auto-scroll and pagination

### Phase 6: Optimization & Polish
1. Audio buffering and streaming optimization
2. Error handling and reconnection
3. Loading states and feedback
4. Performance tuning

## Security Considerations

1. **API Key Management**: All keys stored in environment variables
2. **WebSocket Authentication**: Implement session tokens
3. **Rate Limiting**: Prevent abuse of voice APIs
4. **Input Validation**: Sanitize all user inputs
5. **CORS Configuration**: Restrict origins in production
6. **Sandbox Isolation**: Code execution in isolated containers

## Performance Optimizations

1. **Audio Streaming**: Use chunked streaming for TTS
2. **Caching**: Cache frequent memory queries
3. **WebSocket Pooling**: Reuse connections efficiently
4. **Lazy Loading**: Load 3D assets on demand
5. **Memory Management**: Clean up audio buffers
6. **CDN**: Serve static assets via CDN

## Future Enhancements

1. **Multi-language Support**: Dynamic language detection
2. **Voice Cloning**: Custom user voices
3. **Emotion Detection**: Detect user sentiment from voice
4. **Screen Sharing**: Add video/screen sharing
5. **Mobile App**: React Native version
6. **Offline Mode**: Local STT/TTS fallback
