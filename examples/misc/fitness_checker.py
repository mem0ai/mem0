"""
Simple Fitness Memory Tracker that tracks your fitness progress and knows your health priorities.
Uses Mem0 for memory and GPT-4o for image understanding.

In order to run this file, you need to set up your Mem0 API at Mem0 platform and also need an OpenAI API key.
export OPENAI_API_KEY="your_openai_api_key"
export MEM0_API_KEY="your_mem0_api_key"
"""

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from mem0 import MemoryClient

# Initialize memory
memory_client = MemoryClient(api_key="your-mem0-api-key")
USER_ID = "Anish"

agent = Agent(
    name="Fitness Agent",
    model=OpenAIChat(id="gpt-4o"),
    description="You are a helpful fitness assistant who remembers past logs and gives personalized suggestions for Anish's training and diet.",
    markdown=True,
)


# Store user preferences as memory
def store_user_preferences(conversation: list, user_id: str = USER_ID):
    """Store user preferences from conversation history"""
    memory_client.add(conversation, user_id=user_id, output_format="v1.1")


# Memory-aware assistant function
def fitness_coach(user_input: str, user_id: str = USER_ID):
    memories = memory_client.search(user_input, user_id=user_id)  # Search relevant memories bases on user query
    memory_context = "\n".join(f"- {m['memory']}" for m in memories)

    prompt = f"""You are a fitness assistant who helps Anish with his training, recovery, and diet. You have long-term memory of his health, routines, preferences, and past conversations.

Use your memory to personalize suggestions — consider his constraints, goals, patterns, and lifestyle when responding.

Here is what you remember about {user_id}:
{memory_context}

User query:
{user_input}"""
    response = agent.run(prompt)
    memory_client.add(f"User: {user_input}\nAssistant: {response.content}", user_id=user_id)
    return response.content


# --------------------------------------------------
# Store user preferences and memories
messages = [
    {
        "role": "user",
        "content": "Hi, I’m Anish. I'm 26 years old, 5'10\", and weigh 72kg. I started working out 6 months ago with the goal of building lean muscle.",
    },
    {
        "role": "assistant",
        "content": "Got it — you're 26, 5'10\", 72kg, and on a lean muscle journey. Started gym 6 months ago.",
    },
    {
        "role": "user",
        "content": "I follow a push-pull-legs routine and train 5 times a week. My rest days are Wednesday and Sunday.",
    },
    {
        "role": "assistant",
        "content": "Understood — push-pull-legs split, training 5x/week with rest on Wednesdays and Sundays.",
    },
    {"role": "user", "content": "After push days, I usually eat high-protein and moderate-carb meals to recover."},
    {"role": "assistant", "content": "Noted — high-protein, moderate-carb meals after push workouts."},
    {"role": "user", "content": "For pull days, I take whey protein and eat a banana after training."},
    {"role": "assistant", "content": "Logged — whey protein and banana post pull workouts."},
    {"role": "user", "content": "On leg days, I make sure to have complex carbs like rice or oats."},
    {"role": "assistant", "content": "Noted — complex carbs like rice and oats are part of your leg day meals."},
    {
        "role": "user",
        "content": "I often feel sore after leg days, so I use turmeric milk and magnesium to help with recovery.",
    },
    {"role": "assistant", "content": "I'll remember turmeric milk and magnesium as part of your leg day recovery."},
    {
        "role": "user",
        "content": "Last push day, I did 3x8 bench press at 60kg, 4x12 overhead press, and dips. Felt fatigued after.",
    },
    {
        "role": "assistant",
        "content": "Push day logged — 60kg bench, overhead press, dips. You felt fatigued afterward.",
    },
    {"role": "user", "content": "I prefer light dinners post-workout like tofu, soup, and vegetables."},
    {"role": "assistant", "content": "Got it — light dinners post-workout: tofu, soup, and veggies."},
    {
        "role": "user",
        "content": "I have mild lactose intolerance, so I avoid dairy. I use almond milk or lactose-free whey.",
    },
    {"role": "assistant", "content": "Understood — avoiding regular dairy, using almond milk and lactose-free whey."},
    {
        "role": "user",
        "content": "I get occasional knee pain, so I avoid deep squats and do more hamstring curls and glute bridges on leg days.",
    },
    {
        "role": "assistant",
        "content": "Noted — due to knee discomfort, you substitute deep squats with curls and glute bridges.",
    },
    {"role": "user", "content": "I track sleep and notice poor performance when I sleep less than 6 hours."},
    {"role": "assistant", "content": "Logged — performance drops when you get under 6 hours of sleep."},
    {"role": "user", "content": "I take magnesium supplements to help with muscle recovery and sleep quality."},
    {"role": "assistant", "content": "Remembered — magnesium helps you with recovery and sleep."},
    {"role": "user", "content": "I avoid caffeine after 4 PM because it affects my sleep."},
    {"role": "assistant", "content": "Got it — you avoid caffeine post-4 PM to protect your sleep."},
]
store_user_preferences(messages)

# Example usage with fitness coach
fitness_coach("How much was I lifting for bench press a month ago?")
# OUTPUT: A month ago, you were lifting 55kg for your bench press as part of your push day routine. It looks like you've increased your bench press weight by 5kg since then! Keep up the good work on your journey to gain lean muscle.
fitness_coach("Suggest a post-workout meal, but I’ve had poor sleep last night.")
# OUTPUT: Anish, since you had poor sleep, focus on a recovery-friendly, lactose-free meal: tofu or chicken for protein, paired with quinoa or brown rice for lasting energy. Turmeric almond milk will help with inflammation. Based on your past leg day recovery, continue magnesium, stay well-hydrated, and avoid caffeine after 4PM. Aim for 7–8 hours of sleep, and consider light stretching or a warm bath to ease soreness.
