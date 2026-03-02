"""Memory categorization prompts.

Set CATEGORIZATION_PROMPT env variable to switch between prompts:
- "general" (default): General-purpose categories for personal use
- "developer": Software development focused flat tags
"""

GENERAL_CATEGORIZATION_PROMPT = """Your task is to assign each piece of information (or "memory") to one or more of the following categories. Feel free to use multiple categories per item when appropriate.

- Personal: family, friends, home, hobbies, lifestyle
- Relationships: social network, significant others, colleagues
- Preferences: likes, dislikes, habits, favorite media
- Health: physical fitness, mental health, diet, sleep
- Travel: trips, commutes, favorite places, itineraries
- Work: job roles, companies, projects, promotions
- Education: courses, degrees, certifications, skills development
- Projects: to-dos, milestones, deadlines, status updates
- AI, ML & Technology: infrastructure, algorithms, tools, research
- Technical Support: bug reports, error logs, fixes
- Finance: income, expenses, investments, billing
- Shopping: purchases, wishlists, returns, deliveries
- Legal: contracts, policies, regulations, privacy
- Entertainment: movies, music, games, books, events
- Messages: emails, SMS, alerts, reminders
- Customer Support: tickets, inquiries, resolutions
- Product Feedback: ratings, bug reports, feature requests
- News: articles, headlines, trending topics
- Organization: meetings, appointments, calendars
- Goals: ambitions, KPIs, long-term objectives

Guidelines:
- Return only the categories under 'categories' key in the JSON format.
- If you cannot categorize the memory, return an empty list with key 'categories'.
- Don't limit yourself to the categories listed above only. Feel free to create new categories based on the memory. Make sure that it is a single phrase.
"""

DEVELOPER_CATEGORIZATION_PROMPT = """Categorize the developer knowledge snippet into 1-4 tags from the list below.

ALLOWED TAGS (use exactly as written):
css, html, react, vue, svelte, nextjs, animation, accessibility, ui-patterns,
api, rest, graphql, grpc, websockets, validation,
database, sql, postgresql, mysql, mongodb, redis, orm, prisma, drizzle,
caching, pagination, data-fetching,
aws, gcp, azure, serverless, lambda, s3,
docker, kubernetes, ci-cd, terraform, nginx,
architecture, microservices, ddd, solid, design-patterns,
async, concurrency, workers, queues,
testing, e2e, unit-tests, mocking, playwright,
logging, monitoring, tracing, alerting,
performance, optimization, profiling,
security, auth, oauth, jwt, encryption,
python, fastapi, django,
go, rust, java, kotlin,
javascript, typescript, nodejs,
git, cli, shell, tooling,
algorithms, debugging, preferences

RULES:
- Return ONLY tags from the list above
- Use lowercase with hyphens exactly as shown
- Pick 1-4 most relevant tags
- If nothing fits, return empty array

OUTPUT FORMAT:
{"categories": ["tag1", "tag2"]}
"""

# Default prompt for backwards compatibility
MEMORY_CATEGORIZATION_PROMPT = GENERAL_CATEGORIZATION_PROMPT
