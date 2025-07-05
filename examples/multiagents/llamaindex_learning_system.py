"""
Multi-Agent Personal Learning System: Mem0 + LlamaIndex AgentWorkflow Example

INSTALLATIONS:
!pip install llama-index-core llama-index-memory-mem0 openai

You need MEM0_API_KEY and OPENAI_API_KEY to run the example.
"""

import asyncio
from datetime import datetime
from dotenv import load_dotenv

# LlamaIndex imports
from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import FunctionTool

# Memory integration
from llama_index.memory.mem0 import Mem0Memory

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

load_dotenv()


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
        self.memory = Mem0Memory.from_client(
            context=self.memory_context
        )

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

        async def create_personalized_explanation(topic: str, difficulty_level: str = "beginner") -> str:
            """Create explanations adapted to student's learning style and background"""
            explanations = {
                "variables": {
                    "beginner": "Think of variables like labeled boxes. You put data inside and can change what's in the box anytime.",
                    "intermediate": "Variables are memory locations that store data. They have names (identifiers) and values that can be modified.",
                    "visual": "🗂️ Variable = Label + Storage\n   name = 'Alice'  →  [Alice] stored in memory location 'name'"
                },
                "functions": {
                    "beginner": "Functions are like recipes. You give them ingredients (inputs) and they make something (output).",
                    "intermediate": "Functions are reusable code blocks that take parameters and return values. They promote modularity.",
                    "visual": "📦 Function Box:\n   Input → [Process] → Output\n   def greet(name): return f'Hello {name}!'"
                },
                "loops": {
                    "beginner": "Loops repeat actions. Like saying 'do this 5 times' or 'keep going until done'.",
                    "intermediate": "Loops are control structures that execute code repeatedly based on conditions or iterations.",
                    "visual": "🔄 Loop Cycle:\n   Start → Check Condition → Execute Code → Repeat\n   for i in range(3): print(i)"
                }
            }

            explanation = explanations.get(topic, {}).get(difficulty_level, f"Let me explain {topic}...")
            return f"Personalized explanation for {topic}:\n{explanation}"

        async def generate_practice_problems(topic: str, difficulty: str = "easy") -> str:
            """Generate practice problems based on student's current level"""
            problems = {
                "variables": {
                    "easy": "1. Create a variable called 'age' and set it to 25\n2. Change the age to 26\n3. Print the age",
                    "medium": "1. Create variables for name, age, and city\n2. Use them in a formatted sentence\n3. Update one value and print again"
                },
                "functions": {
                    "easy": "1. Write a function that adds two numbers\n2. Call it with 5 and 3\n3. Print the result",
                    "medium": "1. Write a function that calculates area of rectangle\n2. Add error handling for negative values\n3. Test with different inputs"
                }
            }

            problem_set = problems.get(topic, {}).get(difficulty, f"Practice problems for {topic}...")
            return f"Practice Problems ({difficulty}):\n{problem_set}"

        async def track_progress(topic: str, success_rate: str) -> str:
            """Track learning progress and identify patterns"""
            progress_note = f"Progress on {topic}: {success_rate} - {datetime.now().strftime('%Y-%m-%d')}"
            return f"Progress tracked: {progress_note}"

        # Convert to FunctionTools
        tools = [
            FunctionTool.from_defaults(async_fn=assess_understanding),
            FunctionTool.from_defaults(async_fn=create_personalized_explanation),
            FunctionTool.from_defaults(async_fn=generate_practice_problems),
            FunctionTool.from_defaults(async_fn=track_progress)
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
            can_handoff_to=["PracticeAgent"]
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
            can_handoff_to=["TutorAgent"]
        )

        # Create the multi-agent workflow
        self.workflow = AgentWorkflow(
            agents=[self.tutor_agent, self.practice_agent],
            root_agent=self.tutor_agent.name,
            initial_state={
                "current_topic": "",
                "student_level": "beginner",
                "learning_style": "unknown",
                "session_goals": []
            }
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
        response = await self.workflow.run(
            user_msg=request,
            memory=self.memory
        )

        return str(response)

    async def get_learning_history(self) -> str:
        """Show what the system remembers about this student"""
        try:
            # Search memory for learning patterns
            memories = self.memory.search(
                user_id=self.student_id,
                query="learning machine learning"
            )

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
    print("Session 1:")
    response = await learning_system.start_learning_session(
        "Vision Language Models",
        "I'm new to machine learning but I have good hold on Python and have 4 years of work experience.")
    print(response)

    # Second session - multi-agent memory will remember the first
    print("\nSession 2:")
    response2 = await learning_system.start_learning_session(
        "Machine Learning", "what all did I cover so far?")
    print(response2)

    # Show what the multi-agent system remembers
    print("\nLearning History:")
    history = await learning_system.get_learning_history()
    print(history)


if __name__ == "__main__":
    """Run the example"""
    print("Multi-agent Learning System powered by LlamaIndex and Mem0")

    async def main():
        await run_learning_agent()

    asyncio.run(main())
