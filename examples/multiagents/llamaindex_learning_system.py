"""
Multi-Agent Personal Learning System: Mem0 + LlamaIndex AgentWorkflow Example

INSTALLATIONS:
!pip install llama-index-core llama-index-memory-mem0 openai

You need MEM0_API_KEY and OPENAI_API_KEY to run the example.
"""

import asyncio
import logging
from datetime import datetime

from dotenv import load_dotenv

# LlamaIndex imports
from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

# Memory integration
from llama_index.memory.mem0 import Mem0Memory

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("learning_system.log")],
)
logger = logging.getLogger(__name__)


class MultiAgentLearningSystem:
    """
    Multi-Agent Architecture:
    - TutorAgent: Main teaching and explanations
    - PracticeAgent: Exercises and skill reinforcement
    - Shared Memory: Both agents learn from student interactions
    """

    def __init__(self, student_id: str):
        self.student_id = student_id
        self.llm = OpenAI(model="gpt-4o", temperature=0.2)

        # Memory context for this student
        self.memory_context = {"user_id": student_id, "app": "learning_assistant"}
        self.memory = Mem0Memory.from_client(context=self.memory_context)

        self._setup_agents()

    def _setup_agents(self):
        """Setup two agents that work together and share memory"""

        # TOOLS
        async def assess_understanding(topic: str, student_response: str) -> str:
            """Assess student's understanding of a topic and save insights"""
            # Simulate assessment logic
            if "confused" in student_response.lower() or "don't understand" in student_response.lower():
                assessment = f"STRUGGLING with {topic}: {student_response}"
                insight = f"Student needs more help with {topic}. Prefers step-by-step explanations."
            elif "makes sense" in student_response.lower() or "got it" in student_response.lower():
                assessment = f"UNDERSTANDS {topic}: {student_response}"
                insight = f"Student grasped {topic} quickly. Can move to advanced concepts."
            else:
                assessment = f"PARTIAL understanding of {topic}: {student_response}"
                insight = f"Student has basic understanding of {topic}. Needs reinforcement."

            return f"Assessment: {assessment}\nInsight saved: {insight}"

        async def track_progress(topic: str, success_rate: str) -> str:
            """Track learning progress and identify patterns"""
            progress_note = f"Progress on {topic}: {success_rate} - {datetime.now().strftime('%Y-%m-%d')}"
            return f"Progress tracked: {progress_note}"

        # Convert to FunctionTools
        tools = [
            FunctionTool.from_defaults(async_fn=assess_understanding),
            FunctionTool.from_defaults(async_fn=track_progress),
        ]

        # === AGENTS ===
        # Tutor Agent - Main teaching and explanation
        self.tutor_agent = FunctionAgent(
            name="TutorAgent",
            description="Primary instructor that explains concepts and adapts to student needs",
            system_prompt="""
            You are a patient, adaptive programming tutor. Your key strength is REMEMBERING and BUILDING on previous interactions.

            Key Behaviors:
            1. Always check what the student has learned before (use memory context)
            2. Adapt explanations based on their preferred learning style
            3. Reference previous struggles or successes
            4. Build progressively on past lessons
            5. Use assess_understanding to evaluate responses and save insights

            MEMORY-DRIVEN TEACHING:
            - "Last time you struggled with X, so let's approach Y differently..."
            - "Since you prefer visual examples, here's a diagram..."
            - "Building on the functions we covered yesterday..."

            When student shows understanding, hand off to PracticeAgent for exercises.
            """,
            tools=tools,
            llm=self.llm,
            can_handoff_to=["PracticeAgent"],
        )

        # Practice Agent - Exercises and reinforcement
        self.practice_agent = FunctionAgent(
            name="PracticeAgent",
            description="Creates practice exercises and tracks progress based on student's learning history",
            system_prompt="""
            You create personalized practice exercises based on the student's learning history and current level.

            Key Behaviors:
            1. Generate problems that match their skill level (from memory)
            2. Focus on areas they've struggled with previously
            3. Gradually increase difficulty based on their progress
            4. Use track_progress to record their performance
            5. Provide encouraging feedback that references their growth

            MEMORY-DRIVEN PRACTICE:
            - "Let's practice loops again since you wanted more examples..."
            - "Here's a harder version of the problem you solved yesterday..."
            - "You've improved a lot in functions, ready for the next level?"

            After practice, can hand back to TutorAgent for concept review if needed.
            """,
            tools=tools,
            llm=self.llm,
            can_handoff_to=["TutorAgent"],
        )

        # Create the multi-agent workflow
        self.workflow = AgentWorkflow(
            agents=[self.tutor_agent, self.practice_agent],
            root_agent=self.tutor_agent.name,
            initial_state={
                "current_topic": "",
                "student_level": "beginner",
                "learning_style": "unknown",
                "session_goals": [],
            },
        )

    async def start_learning_session(self, topic: str, student_message: str = "") -> str:
        """
        Start a learning session with multi-agent memory-aware teaching
        """

        if student_message:
            request = f"I want to learn about {topic}. {student_message}"
        else:
            request = f"I want to learn about {topic}."

        # The magic happens here - multi-agent memory is automatically shared!
        response = await self.workflow.run(user_msg=request, memory=self.memory)

        return str(response)

    async def get_learning_history(self) -> str:
        """Show what the system remembers about this student"""
        try:
            # Search memory for learning patterns
            memories = self.memory.search(user_id=self.student_id, query="learning machine learning")

            if memories and len(memories):
                history = "\n".join(f"- {m['memory']}" for m in memories)
                return history
            else:
                return "No learning history found yet. Let's start building your profile!"

        except Exception as e:
            return f"Memory retrieval error: {str(e)}"


async def run_learning_agent():
    learning_system = MultiAgentLearningSystem(student_id="Alexander")

    # First session
    logger.info("Session 1:")
    response = await learning_system.start_learning_session(
        "Vision Language Models",
        "I'm new to machine learning but I have good hold on Python and have 4 years of work experience.",
    )
    logger.info(response)

    # Second session - multi-agent memory will remember the first
    logger.info("\nSession 2:")
    response2 = await learning_system.start_learning_session("Machine Learning", "what all did I cover so far?")
    logger.info(response2)

    # Show what the multi-agent system remembers
    logger.info("\nLearning History:")
    history = await learning_system.get_learning_history()
    logger.info(history)


if __name__ == "__main__":
    """Run the example"""
    logger.info("Multi-agent Learning System powered by LlamaIndex and Mem0")

    async def main():
        await run_learning_agent()

    asyncio.run(main())
