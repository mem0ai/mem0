"""
Meta-Cognitive Adaptive Memory Demo.

This script demonstrates the self-learning memory parameter optimization system.
It simulates user interactions with feedback signals to show how the system
adapts forgetting curves and importance weights for different users.

Author: Hongyi Zhou
"""

import os
import sys
import time
from typing import Dict, Any
import random

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mem0 import Memory
from mem0.configs.base import MemoryConfig


def simulate_user_feedback(memory_response: Dict, turn_number: int) -> float:
    """
    Simulate implicit user feedback as a reward signal (0.0 - 1.0).
    
    In a real application, this would be derived from:
    - User点赞/thumbs up
    - Follow-up questions (engagement)
    - Conversation continuation length
    - Task completion success
    
    For demo purposes, we simulate based on:
    - Higher scores for relevant memories being retrieved
    - Penalty for too many or too few results
    """
    results = memory_response.get("results", [])
    num_results = len(results)
    
    # Ideal: 3-7 relevant memories retrieved
    if 3 <= num_results <= 7:
        base_reward = 0.8
    elif 1 <= num_results <= 10:
        base_reward = 0.6
    else:
        base_reward = 0.3
    
    # Bonus if high-scoring memories are present
    if results and any(r.get("score", 0) > 0.7 for r in results):
        base_reward += 0.15
    
    # Add some noise to simulate real user variability
    noise = random.gauss(0, 0.05)
    reward = max(0.0, min(1.0, base_reward + noise))
    
    return reward


def run_meta_cognitive_demo():
    """
    Run a demonstration of the meta-cognitive adaptive memory system.
    
    This shows:
    1. Initial memory operations with default parameters
    2. Feedback collection and parameter adaptation
    3. Improved performance over time as system learns user preferences
    """
    print("=" * 80)
    print("META-COGNITIVE ADAPTIVE MEMORY DEMO")
    print("Demonstrating self-learning memory parameter optimization")
    print("=" * 80)
    print()
    
    # Initialize memory with cognitive features enabled
    config = MemoryConfig(
        enable_cognitive_features=True,
        vector_store={
            "provider": "qdrant",
            "config": {
                "host": "localhost",
                "port": 6333,
            }
        },
        llm={
            "provider": "openai",
            "config": {"model": "gpt-4o-mini"}
        }
    )
    
    try:
        memory = Memory(config=config)
    except Exception as e:
        print(f"⚠️  Failed to initialize Memory (Qdrant may not be running): {e}")
        print("\n📝 To run this demo:")
        print("   docker run -d -p 6333:6333 qdrant/qdrant")
        print("   export OPENAI_API_KEY='your-key'")
        print("   python examples/meta_cognitive_demo.py")
        return
    
    user_id = "demo_user_001"
    
    # Phase 1: Initial interactions (Exploration phase)
    print("\n🧪 PHASE 1: EXPLORATION (Initial Interactions)")
    print("-" * 80)
    print("System uses default parameters and explores variations...")
    print()
    
    initial_memories = [
        {"role": "user", "content": "I love drinking coffee every morning"},
        {"role": "assistant", "content": "That's great! Coffee is a wonderful way to start the day."},
        {"role": "user", "content": "I prefer working in quiet environments"},
        {"role": "assistant", "content": "Quiet spaces can really boost productivity."},
        {"role": "user", "content": "My favorite programming language is Python"},
    ]
    
    for i, msg in enumerate(initial_memories[:3], 1):
        response = memory.add([msg], user_id=user_id)
        print(f"✓ Added memory {i}: {msg['content'][:50]}...")
        time.sleep(0.5)
    
    # Phase 2: Search with feedback collection (Learning phase)
    print("\n\n📚 PHASE 2: LEARNING (Search + Feedback Collection)")
    print("-" * 80)
    print("System collects feedback to optimize parameters...")
    print()
    
    queries = [
        "What do I like to drink?",
        "What kind of work environment do I prefer?",
        "What programming language do I use?",
    ]
    
    feedback_history = []
    
    for i, query in enumerate(queries, 1):
        print(f"\n🔍 Query {i}: '{query}'")
        
        # Perform search
        response = memory.search(query, user_id=user_id, top_k=5)
        results = response.get("results", [])
        
        print(f"   Retrieved {len(results)} memories")
        if results:
            print(f"   Top result score: {results[0].get('score', 0):.4f}")
        
        # Simulate user feedback
        reward = simulate_user_feedback(response, i)
        feedback_history.append(reward)
        print(f"   💡 Simulated user feedback (reward): {reward:.3f}")
        
        # Extract current parameters used
        params_used, _ = memory.meta_learner.get_optimized_params(user_id)
        print(f"   ⚙️  Current decay factor S: {params_used:.2f}")
        
        time.sleep(0.5)
    
    # Phase 3: Parameter adaptation demonstration
    print("\n\n🔄 PHASE 3: ADAPTATION (Parameter Optimization)")
    print("-" * 80)
    print("System updates parameters based on collected feedback...")
    print()
    
    # Manually trigger parameter updates (in real system, this happens automatically)
    for i, reward in enumerate(feedback_history):
        # Get the parameters that were used for this trial
        current_S, current_weights = memory.meta_learner.get_optimized_params(user_id)
        
        # Create trial params (simulating what was used)
        trial_params = {
            "S": current_S * (1 + random.gauss(0, 0.1)),  # Add exploration noise
            "weights": current_weights.copy()
        }
        
        # Record feedback
        memory.meta_learner.record_feedback(user_id, trial_params, reward)
        
        print(f"   Trial {i+1}: Reward={reward:.3f} → Updated best S={current_S:.2f}")
    
    # Phase 4: Final optimized state
    print("\n\n✨ PHASE 4: OPTIMIZED STATE")
    print("-" * 80)
    print("Final learned parameters for this user:")
    print()
    
    final_S, final_weights = memory.meta_learner.get_optimized_params(user_id)
    user_state = memory.meta_learner.get_user_state(user_id)
    
    print(f"   🎯 Optimal Decay Factor (S): {final_S:.2f}")
    print(f"   📊 Learned Importance Weights:")
    for key, value in final_weights.items():
        bar = "█" * int(value * 20)
        print(f"      {key:10s}: {value:.3f} {bar}")
    
    print(f"\n   📈 Confidence in parameters: {user_state.confidence:.2%}")
    print(f"   📝 Total trials recorded: {len(user_state.trials)}")
    
    # Phase 5: Comparison demonstration
    print("\n\n📊 PHASE 5: PERFORMANCE COMPARISON")
    print("-" * 80)
    print("Comparing retrieval quality before vs after adaptation...")
    print()
    
    test_query = "What are my preferences?"
    
    # Search with optimized parameters
    optimized_response = memory.search(test_query, user_id=user_id, top_k=5)
    opt_results = optimized_response.get("results", [])
    
    print(f"   Query: '{test_query}'")
    print(f"   ✓ Optimized system retrieved: {len(opt_results)} memories")
    if opt_results:
        avg_score = sum(r.get("score", 0) for r in opt_results) / len(opt_results)
        print(f"   ✓ Average relevance score: {avg_score:.4f}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\n💡 Key Takeaways:")
    print("   • The system adapts memory parameters per user automatically")
    print("   • Feedback signals drive parameter optimization (RL-style)")
    print("   • Different users get personalized forgetting curves")
    print("   • Over time, retrieval quality improves for each individual")
    print("\n📝 Next Steps:")
    print("   • Integrate real user feedback (clicks, ratings, engagement)")
    print("   • Run long-term A/B tests to validate improvement")
    print("   • Extend to domain-specific adaptation (medical vs casual)")
    print()


if __name__ == "__main__":
    run_meta_cognitive_demo()
