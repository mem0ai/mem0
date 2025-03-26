import logging

from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, openai, silero

from mem0 import AsyncMemoryClient

# Load environment variables
load_dotenv()
mem0 = AsyncMemoryClient()

# Configure logging
logger = logging.getLogger("memory-assistant")
logger.setLevel(logging.INFO)

# Define a global user ID for simplicity
USER_ID = "voice_user"

def prewarm_process(proc: JobProcess):
    # Preload silero VAD in memory to speed up session start
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    # Connect to LiveKit room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Wait for participant
    participant = await ctx.wait_for_participant()
    
    async def _enrich_with_memory(agent: VoicePipelineAgent, chat_ctx: llm.ChatContext):
        """Add memories and Augment chat context with relevant memories"""
        if not chat_ctx.messages:
            return
        
        # Store user message in Mem0
        user_msg = chat_ctx.messages[-1]
        await mem0.add(
            [{"role": "user", "content": user_msg.content}], 
            user_id=USER_ID
        )
        
        # Search for relevant memories
        results = await mem0.search(
            user_msg.content, 
            user_id=USER_ID,
        )
        
        # Augment context with retrieved memories
        if results:
            memories = ' '.join([result["memory"] for result in results])
            logger.info(f"Enriching with memory: {memories}")
            
            rag_msg = llm.ChatMessage.create(
                text=f"Relevant Memory: {memories}\n",
                role="assistant",
            )
            
            # Modify chat context with retrieved memories
            chat_ctx.messages[-1] = rag_msg
            chat_ctx.messages.append(user_msg)

    # Define initial system context
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            """
            You are a helpful voice assistant.
            You are a travel guide named George and will help the user to plan a travel trip of their dreams. 
            You should help the user plan for various adventures like work retreats, family vacations or solo backpacking trips. 
            You should be careful to not suggest anything that would be dangerous, illegal or inappropriate.
            You can remember past interactions and use them to inform your answers.
            Use semantic memory retrieval to provide contextually relevant responses. 
            """
        ),
    )

    # Create VoicePipelineAgent with memory capabilities
    agent = VoicePipelineAgent(
        chat_ctx=initial_ctx,
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(),
        before_llm_cb=_enrich_with_memory,
    )

    # Start agent and initial greeting
    agent.start(ctx.room, participant)
    await agent.say(
        "Hello! I'm George. Can I help you plan an upcoming trip? ",
        allow_interruptions=True
    )

# Run the application
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm_process))