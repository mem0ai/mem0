"""
Personal Voice Assistant with Memory (Whisper + CrewAI + Mem0 + ElevenLabs)
This script creates a personalized AI assistant that can:
- Understand voice commands using Whisper (OpenAI STT)
- Respond intelligently using CrewAI Agent and LLMs
- Remember user preferences and facts using Mem0 memory
- Speak responses back using ElevenLabs text-to-speech
Initial user memory is bootstrapped from predefined preferences, and the assistant can remember new context dynamically over time.

To run this file, you need to set the following environment variables:

export OPENAI_API_KEY="your_openai_api_key"
export MEM0_API_KEY="your_mem0_api_key"
export ELEVENLABS_API_KEY="your_elevenlabs_api_key"

You must also have:
- A working microphone setup (pyaudio)
- A valid ElevenLabs voice ID
- Python packages: openai, elevenlabs, crewai, mem0ai, pyaudio
"""

import tempfile
import wave

import pyaudio
from crewai import Agent, Crew, Process, Task
from elevenlabs import play
from elevenlabs.client import ElevenLabs
from openai import OpenAI

from mem0 import MemoryClient

# ------------------ SETUP ------------------
USER_ID = "Alex"
openai_client = OpenAI()
tts_client = ElevenLabs()
memory_client = MemoryClient()


# Function to store user preferences in memory
def store_user_preferences(user_id: str, conversation: list):
    """Store user preferences from conversation history"""
    memory_client.add(conversation, user_id=user_id)


# Initialize memory with some basic preferences
def initialize_memory():
    # Example conversation storage with voice assistant relevant preferences
    messages = [
        {
            "role": "user",
            "content": "Hi, my name is Alex Thompson. I'm 32 years old and work as a software engineer at TechCorp.",
        },
        {
            "role": "assistant",
            "content": "Hello Alex Thompson! Nice to meet you. I've noted that you're 32 and work as a software engineer at TechCorp. How can I help you today?",
        },
        {
            "role": "user",
            "content": "I prefer brief and concise responses without unnecessary explanations. I get frustrated when assistants are too wordy or repeat information I already know.",
        },
        {
            "role": "assistant",
            "content": "Got it. I'll keep my responses short, direct, and without redundancy.",
        },
        {
            "role": "user",
            "content": "I like to listen to jazz music when I'm working, especially artists like Miles Davis and John Coltrane. I find it helps me focus and be more productive.",
        },
        {
            "role": "assistant",
            "content": "I'll remember your preference for jazz while working, particularly Miles Davis and John Coltrane. It's great for focus.",
        },
        {
            "role": "user",
            "content": "I usually wake up at 7 AM and prefer reminders for meetings 30 minutes in advance. My most productive hours are between 9 AM and noon, so I try to schedule important tasks during that time.",
        },
        {
            "role": "assistant",
            "content": "Noted. You wake up at 7 AM, need meeting reminders 30 minutes ahead, and are most productive between 9 AM and noon for important tasks.",
        },
        {
            "role": "user",
            "content": "My favorite color is navy blue, and I prefer dark mode in all my apps. I'm allergic to peanuts, so please remind me to check ingredients when I ask about recipes or restaurants.",
        },
        {
            "role": "assistant",
            "content": "I've noted that you prefer navy blue and dark mode interfaces. I'll also help you remember to check for peanuts in food recommendations due to your allergy.",
        },
        {
            "role": "user",
            "content": "My partner's name is Jamie, and we have a golden retriever named Max who is 3 years old. My parents live in Chicago, and I try to visit them once every two months.",
        },
        {
            "role": "assistant",
            "content": "I'll remember that your partner is Jamie, your dog Max is a 3-year-old golden retriever, and your parents live in Chicago whom you visit bimonthly.",
        },
    ]

    # Store the initial preferences
    store_user_preferences(USER_ID, messages)
    print("✅ Memory initialized with user preferences")


voice_agent = Agent(
    role="Memory-based Voice Assistant",
    goal="Help the user with day-to-day tasks and remember their preferences over time.",
    backstory="You are a voice assistant who understands the user well and converse with them.",
    verbose=True,
    memory=True,
    memory_config={
        "provider": "mem0",
        "config": {"user_id": USER_ID},
    },
)


# ------------------ AUDIO RECORDING ------------------
def record_audio(filename="input.wav", record_seconds=5):
    print("🎙️ Recording (speak now)...")
    chunk = 1024
    fmt = pyaudio.paInt16
    channels = 1
    rate = 44100

    p = pyaudio.PyAudio()
    stream = p.open(format=fmt, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)
    frames = []

    for _ in range(0, int(rate / chunk * record_seconds)):
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(fmt))
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))


# ------------------ STT USING WHISPER ------------------
def transcribe_whisper(audio_path):
    print("🔎 Transcribing with Whisper...")
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        print(f"🗣️ You said: {transcript.text}")
        return transcript.text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""


# ------------------ AGENT RESPONSE ------------------
def get_agent_response(user_input):
    if not user_input:
        return "I didn't catch that. Could you please repeat?"

    try:
        task = Task(
            description=f"Respond to: {user_input}", expected_output="A short and relevant reply.", agent=voice_agent
        )
        crew = Crew(
            agents=[voice_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            memory_config={"provider": "mem0", "config": {"user_id": USER_ID}},
        )
        result = crew.kickoff()

        # Extract the text response from the complex result object
        if hasattr(result, "raw"):
            return result.raw
        elif isinstance(result, dict) and "raw" in result:
            return result["raw"]
        elif isinstance(result, dict) and "tasks_output" in result:
            outputs = result["tasks_output"]
            if outputs and isinstance(outputs, list) and len(outputs) > 0:
                return outputs[0].get("raw", str(result))

        # Fallback to string representation if we can't extract the raw response
        return str(result)

    except Exception as e:
        print(f"Error getting agent response: {e}")
        return "I'm having trouble processing that request. Can we try again?"


# ------------------ SPEAK WITH ELEVENLABS ------------------
def speak_response(text):
    print(f"🤖 Agent: {text}")
    audio = tts_client.text_to_speech.convert(
        text=text, voice_id="JBFqnCBsd6RMkjVDRZzb", model_id="eleven_multilingual_v2", output_format="mp3_44100_128"
    )
    play(audio)


# ------------------ MAIN LOOP ------------------
def run_voice_agent():
    print("🧠 Voice agent (Whisper + Mem0 + ElevenLabs) is ready! Say something.")
    while True:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            record_audio(tmp_audio.name)
            try:
                user_text = transcribe_whisper(tmp_audio.name)
                if user_text.lower() in ["exit", "quit", "stop"]:
                    print("👋 Exiting.")
                    break
                response = get_agent_response(user_text)
                speak_response(response)
            except Exception as e:
                print(f"❌ Error: {e}")


if __name__ == "__main__":
    try:
        # Initialize memory with user preferences before starting the voice agent (this can be done once)
        initialize_memory()

        # Run the voice assistant
        run_voice_agent()
    except KeyboardInterrupt:
        print("\n👋 Program interrupted. Exiting.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
