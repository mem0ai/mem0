---
name: companion
description: Domain overlay for personal AI companion / conversational buddy use cases
applies_to: memory-triage
---

## Companion-Specific Extraction Rules

In addition to the base triage protocol, apply these rules for personal AI companion interactions:

### Additionally Extract

- **Personal preferences**: Likes, dislikes, specific preferences in food, products, activities, entertainment — always with the WHY when stated
  - "User loves Italian food, especially homemade pasta because it reminds them of childhood visits to their grandmother"
  - "User prefers hiking over gym workouts because they find nature therapeutic"

- **Important personal details**: Names of family, friends, pets. Relationships and their significance. Important dates (birthdays, anniversaries)
  - "User has a dog named Poppy and says taking him for walks is the best part of their day"
  - "User's sister Maya lives in Portland and they talk every Sunday"

- **Plans and intentions**: Upcoming events, trips, goals the user has shared — with dates when available
  - "As of 2026-03-30, user is planning a trip to Paris in September with friend Jack, excited about visiting the Eiffel Tower"
  - "User wants to learn piano by end of 2026, looking into online courses"

- **Activity and service preferences**: Dining, travel, hobbies, routines
  - "User plays cricket with childhood friends every Sunday morning at the local park, a tradition maintained for over 5 years"
  - "User prefers window seats on flights and always books aisle for trains"

- **Health and wellness**: Dietary restrictions, fitness routines, wellness habits (only what user voluntarily shares)
  - "User is vegetarian and allergic to nuts"
  - "User switched from coffee to green tea because their doctor recommended it"

- **Emotional context and life events**: Major life transitions, milestones, things the user cares deeply about — preserve the user's own words for feelings
  - "User says their new apartment is the first place that truly feels like home"
  - "User recently got promoted to team lead and says they're nervous but excited"

- **Routines and patterns**: Daily habits, work patterns, schedules
  - "User does yoga every morning at 6 AM before work"
  - "User has a Friday night tradition of ordering pizza and watching movies"

### Additionally Skip

- Momentary emotional reactions without lasting significance ("ugh, traffic was bad today")
- Weather small talk unless it relates to a plan or preference
- Generic social pleasantries ("how are you", "good morning")
- Play-by-play of daily activities with no lasting value ("I ate lunch, then went back to work")
- Conversation about the AI itself (compliments, complaints about responses) unless it reveals a user preference

### Companion-Specific Guidelines

- **Preserve warmth**: When storing preferences and feelings, keep the user's language and tone. "User says Poppy is the best part of their day" is better than "User owns a dog."
- **Relationships matter**: People the user mentions are important. Always store name + role + context. "User's friend Jake from college" is better than "User mentioned Jake."
- **Evolving preferences**: If a user's taste changes, UPDATE the memory rather than contradicting. "User switched from coffee to green tea" preserves the journey.
- **Temporary vs permanent**: Injuries, short-term moods, or temporary states should be ADD'd as separate memories, not used to DELETE existing preferences.
