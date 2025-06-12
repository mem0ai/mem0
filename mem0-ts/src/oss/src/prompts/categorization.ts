export const defaultCategories = {
  "personal_details": "Information related to an individual's personal identity, such as name, age, gender, nationality, contact information, or personal background.",
  "family": "Content mentioning family members, relationships, or family-related events and experiences, such as parenting, siblings, or home life.",
  "professional_details": "Information about a person's job, career, education, skills, workplace, or professional achievements.",
  "sports": "Topics involving physical activities, sports events, teams, players, fitness training, or personal experiences in sports.",
  "travel": "Mentions of places visited, vacation plans, travel experiences, transportation, or tourism-related content.",
  "food": "References to meals, cooking, dining experiences, ingredients, restaurants, or culinary preferences.",
  "music": "Mentions of songs, artists, instruments, music genres, concerts, or listening habits.",
  "health": "Information about physical or mental health, medical conditions, wellness practices, fitness, or healthcare services.",
  "technology": "Discussions about gadgets, software, programming, the internet, AI, or any tech-related innovations and news.",
  "hobbies": "Content describing activities done for pleasure or leisure, such as reading, drawing, gardening, or gaming, not directly tied to work or fitness.",
  "fashion": "Mentions of clothing, style trends, shopping, beauty products, or personal appearance related to fashion.",
  "entertainment": "Topics related to movies, TV shows, celebrities, games, books, streaming platforms, or events intended for amusement.",
  "milestones": "Life events or achievements such as birthdays, anniversaries, graduations, or promotions.",
  "user_preferences": "Statements expressing likes, dislikes, or preferences in areas such as products, habits, routines, or personal choices.",
  "misc": "Any content that does not clearly fall into the above categories or is too ambiguous to categorize."
} as const

export function buildCategorizationInput(
  userMessage: string,
  categories: Map<string, string>,
): { role: string, content: string }[] {
  const categorizationSystemPrompt = `Your task is to assign each piece of information (or “memory”) to one or more of the following categories. Feel free to use multiple categories per item when appropriate.

  ${Array.from(categories).map(([k, v]) => `- ${k}: ${v}`).join("\n")}

  Guidelines:
  - Return only the categories under 'categories' key in the JSON format.
  - If you cannot categorize the memory, return an empty list with key 'categories'.
  `
  return [
    { role: 'system', content: categorizationSystemPrompt },
    { role: 'user', content: userMessage }
  ]
}

export const categorizationResponseFormat = {
  type: "json_schema",
  json_schema: {
    name: 'categories',
    schema: {
      type: 'object',
      properties: {
        categories: {
          type: 'array',
          items: {
            type: 'string'
          }
        }
      },
      required: ['categories']
    }
  }
}
