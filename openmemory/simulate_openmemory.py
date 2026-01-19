from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

# First two embeds (concurrency optional, but sequential is fine)
for _ in range(2):
    client.embeddings.create(
        model="text-embedding-bge-m3",
        input="""Key Functional Similarities
Despite the reordering, the requests are identical in all critical functional aspects:

Endpoint: Both are POST requests to /v1/chat/completions.

Model: Both use the identical model: "liquidai_lfm2.5-1.2b-instruct".

Messages (Input): Both contain the exact same system and user messages.

Temperature: Both are set to the exact same value: "temperature": 0.

Streaming: Both are disabled: "stream": false.

Response Format: Both demand the exact same JSON schema output (named "MemoryCategories," strictly enforced, with an array of strings called "categories").

💡 Missing Parameter
The only other difference is that the OPENMEMORY API TEST payload is missing the max_tokens parameter, which was set to 2000 in the CURL API TEST.

Impact: Since max_tokens is often an optional parameter, the OPENMEMORY API TEST will likely default to the model's maximum allowed tokens (or a service-defined default), whereas the CURL API TEST explicitly limits it to 2000. For practical purposes here, since the request is likely not generating 2000 tokens of output, the lack of this parameter is unlikely to change the result.

In conclusion, for the purpose of running the chat completion task, these two requests are equivalent and should produce the same output (assuming the service defaults for max_tokens are high enough).

Would you like me to compare this to a third request, perhaps one that uses a different model or temperature?""",
        dimensions=1536,
        encoding_format="base64"
    )

# Chat call
response = client.chat.completions.create(
    model="liquidai_lfm2.5-1.2b-instruct",
    messages=[
        {"role": "system", "content": """Your task is to assign each piece of information (or “memory”) to one or more of the following categories. Feel free to use multiple categories per item when appropriate.\n\n- Personal: family, friends, home, hobbies, lifestyle\n- Relationships: social network, significant others, colleagues\n- Preferences: likes, dislikes, habits, favorite media\n- Health: physical fitness, mental health, diet, sleep\n- Travel: trips, commutes, favorite places, itineraries\n- Work: job roles, companies, projects, promotions\n- Education: courses, degrees, certifications, skills development\n- Projects: to‑dos, milestones, deadlines, status updates\n- AI, ML & Technology: infrastructure, algorithms, tools, research\n- Technical Support: bug reports, error logs, fixes\n- Finance: income, expenses, investments, billing\n- Shopping: purchases, wishlists, returns, deliveries\n- Legal: contracts, policies, regulations, privacy\n- Entertainment: movies, music, games, books, events\n- Messages: emails, SMS, alerts, reminders\n- Customer Support: tickets, inquiries, resolutions\n- Product Feedback: ratings, bug reports, feature requests\n- News: articles, headlines, trending topics\n- Organization: meetings, appointments, calendars\n- Goals: ambitions, KPIs, long‑term objectives\n\nGuidelines:\n- Return ONLY a comma-delimited list of categories (e.g., Personal, Preferences, Work).\n- Do not include any JSON, brackets, quotes, explanations, or additional text.\n- If you cannot categorize the memory, return an empty response.\n- Don't limit yourself to the categories listed above only. Feel free to create new categories based on the memory. Make sure each category is a single concise phrase."""}
    ],
    temperature=0
)

for _ in range(2):
    client.embeddings.create(
        model="text-embedding-bge-m3",
        input="""Here is a structured memory test sequence you can use:🎯 Step 1: Add the MemoryInput a distinct fact that the AI wouldn't already know. This is your memory to be stored.Memory Text to $\text{add\_memories}$:"The main technical requirement for the $\text{Aurora}$ project is that the backend must be implemented using a Rust microservice architecture, and it must integrate with our existing $\text{PostgreSQL}$ database cluster using the $\text{sqlx}$ library."\
""",
        dimensions=1536,
        encoding_format="base64"
    )

# Chat call
response = client.chat.completions.create(
    model="liquidai_lfm2.5-1.2b-instruct",
    messages=[
        {"role": "system", "content": """Your task is to assign each piece of information (or “memory”) to one or more of the following categories. Feel free to use multiple categories per item when appropriate.\n\n- Personal: family, friends, home, hobbies, lifestyle\n- Relationships: social network, significant others, colleagues\n- Preferences: likes, dislikes, habits, favorite media\n- Health: physical fitness, mental health, diet, sleep\n- Travel: trips, commutes, favorite places, itineraries\n- Work: job roles, companies, projects, promotions\n- Education: courses, degrees, certifications, skills development\n- Projects: to‑dos, milestones, deadlines, status updates\n- AI, ML & Technology: infrastructure, algorithms, tools, research\n- Technical Support: bug reports, error logs, fixes\n- Finance: income, expenses, investments, billing\n- Shopping: purchases, wishlists, returns, deliveries\n- Legal: contracts, policies, regulations, privacy\n- Entertainment: movies, music, games, books, events\n- Messages: emails, SMS, alerts, reminders\n- Customer Support: tickets, inquiries, resolutions\n- Product Feedback: ratings, bug reports, feature requests\n- News: articles, headlines, trending topics\n- Organization: meetings, appointments, calendars\n- Goals: ambitions, KPIs, long‑term objectives\n\nGuidelines:\n- Return ONLY a comma-delimited list of categories (e.g., Personal, Preferences, Work).\n- Do not include any JSON, brackets, quotes, explanations, or additional text.\n- If you cannot categorize the memory, return an empty response.\n- Don't limit yourself to the categories listed above only. Feel free to create new categories based on the memory. Make sure each category is a single concise phrase."""},
        {"role": "user", "content": """Here is a structured memory test sequence you can use:🎯 Step 1: Add the MemoryInput a distinct fact that the AI wouldn't already know. This is your memory to be stored.Memory Text to $\text{add\_memories}$:"The main technical requirement for the $\text{Aurora}$ project is that the backend must be implemented using a Rust microservice architecture, and it must integrate with our existing $\text{PostgreSQL}$ database cluster using the $\text{sqlx}$ library."\
"""}
    ],
    temperature=0
)

for _ in range(2):
    client.embeddings.create(
        model="text-embedding-bge-m3",
        input="""That's a great request! OpenMemory, powered by Mem0, is designed to store facts and context persistently for your AI clients.

To effectively test the memory storage and retrieval functionality, you should input a specific, non-obvious piece of information about a user or a project, and then query for it in a semantically different way to see if the system can correctly retrieve the relevant memory.""",
        dimensions=1536,
        encoding_format="base64"
    )

# Chat call
response = client.chat.completions.create(
    model="liquidai_lfm2.5-1.2b-instruct",
    messages=[
        {"role": "system", "content": """Your task is to assign each piece of information (or “memory”) to one or more of the following categories. Feel free to use multiple categories per item when appropriate.\n\n- Personal: family, friends, home, hobbies, lifestyle\n- Relationships: social network, significant others, colleagues\n- Preferences: likes, dislikes, habits, favorite media\n- Health: physical fitness, mental health, diet, sleep\n- Travel: trips, commutes, favorite places, itineraries\n- Work: job roles, companies, projects, promotions\n- Education: courses, degrees, certifications, skills development\n- Projects: to‑dos, milestones, deadlines, status updates\n- AI, ML & Technology: infrastructure, algorithms, tools, research\n- Technical Support: bug reports, error logs, fixes\n- Finance: income, expenses, investments, billing\n- Shopping: purchases, wishlists, returns, deliveries\n- Legal: contracts, policies, regulations, privacy\n- Entertainment: movies, music, games, books, events\n- Messages: emails, SMS, alerts, reminders\n- Customer Support: tickets, inquiries, resolutions\n- Product Feedback: ratings, bug reports, feature requests\n- News: articles, headlines, trending topics\n- Organization: meetings, appointments, calendars\n- Goals: ambitions, KPIs, long‑term objectives\n\nGuidelines:\n- Return ONLY a comma-delimited list of categories (e.g., Personal, Preferences, Work).\n- Do not include any JSON, brackets, quotes, explanations, or additional text.\n- If you cannot categorize the memory, return an empty response.\n- Don't limit yourself to the categories listed above only. Feel free to create new categories based on the memory. Make sure each category is a single concise phrase."""},
        {"role": "user", "content": """That's a great request! OpenMemory, powered by Mem0, is designed to store facts and context persistently for your AI clients.

To effectively test the memory storage and retrieval functionality, you should input a specific, non-obvious piece of information about a user or a project, and then query for it in a semantically different way to see if the system can correctly retrieve the relevant memory."""}
    ],
    temperature=0
)

for _ in range(2):
    client.embeddings.create(
        model="text-embedding-bge-m3",
        input="""You're right, let's keep it simple. The best way to test the categorization feature is to add two memories that clearly fall into different, custom-defined categories.OpenMemory (Mem0) typically uses an LLM to automatically assign categories to new memories based on the content and a list of defined categories.📝 Test Sequence for CategorizationThis sequence tests the automatic assignment of categories based on the memory's content.Step 1: Define Custom CategoriesFirst, ensure your OpenMemory setup (if you're using the platform version or the open-source version with a connected LLM) is configured with these custom categories. For a simpler test, you can often define them via the SDK's project.update() method.Category 1: $\text{Work\_Project\_Info}$Category 2: $\text{User\_Preferences}$""",
        dimensions=1536,
        encoding_format="base64"
    )

# Chat call
response = client.chat.completions.create(
    model="liquidai_lfm2.5-1.2b-instruct",
    messages=[
        {"role": "system", "content": """Your task is to assign each piece of information (or “memory”) to one or more of the following categories. Feel free to use multiple categories per item when appropriate.\n\n- Personal: family, friends, home, hobbies, lifestyle\n- Relationships: social network, significant others, colleagues\n- Preferences: likes, dislikes, habits, favorite media\n- Health: physical fitness, mental health, diet, sleep\n- Travel: trips, commutes, favorite places, itineraries\n- Work: job roles, companies, projects, promotions\n- Education: courses, degrees, certifications, skills development\n- Projects: to‑dos, milestones, deadlines, status updates\n- AI, ML & Technology: infrastructure, algorithms, tools, research\n- Technical Support: bug reports, error logs, fixes\n- Finance: income, expenses, investments, billing\n- Shopping: purchases, wishlists, returns, deliveries\n- Legal: contracts, policies, regulations, privacy\n- Entertainment: movies, music, games, books, events\n- Messages: emails, SMS, alerts, reminders\n- Customer Support: tickets, inquiries, resolutions\n- Product Feedback: ratings, bug reports, feature requests\n- News: articles, headlines, trending topics\n- Organization: meetings, appointments, calendars\n- Goals: ambitions, KPIs, long‑term objectives\n\nGuidelines:\n- Return ONLY a comma-delimited list of categories (e.g., Personal, Preferences, Work).\n- Do not include any JSON, brackets, quotes, explanations, or additional text.\n- If you cannot categorize the memory, return an empty response.\n- Don't limit yourself to the categories listed above only. Feel free to create new categories based on the memory. Make sure each category is a single concise phrase."""},
        {"role": "user", "content": """You're right, let's keep it simple. The best way to test the categorization feature is to add two memories that clearly fall into different, custom-defined categories.OpenMemory (Mem0) typically uses an LLM to automatically assign categories to new memories based on the content and a list of defined categories.📝 Test Sequence for CategorizationThis sequence tests the automatic assignment of categories based on the memory's content.Step 1: Define Custom CategoriesFirst, ensure your OpenMemory setup (if you're using the platform version or the open-source version with a connected LLM) is configured with these custom categories. For a simpler test, you can often define them via the SDK's project.update() method.Category 1: $\text{Work\_Project\_Info}$Category 2: $\text{User\_Preferences}$"""}
    ],
    temperature=0
)

for _ in range(2):
    client.embeddings.create(
        model="text-embedding-bge-m3",
        input="""Sure! Let's consider an example with a slightly modified endpoint, model and messages.

Endpoint: This is now a GET request to /v1/chat/completions/{id}.

Model: We use the same model as before but this time it's "liquidai_lfm2.5-1.2b-instruct".

Messages (Input): The system and user messages are slightly different, with an additional message from the user asking for a list of programming languages.

Temperature: It is set to 0.5 instead of 0 as before.

Streaming: Streaming is enabled: "stream": true.

Response Format: We demand the same JSON schema output (named "MemoryCategories", strictly enforced, with an array of strings called "categories").

The only difference here compared to your original request is that we're now using a GET method instead of POST and are passing in a chat completion ID.

Impact: The impact on the output will be slightly different due to these changes. With temperature set at 0.5, it might generate more diverse responses than with a lower temperature (like 0). Streaming is enabled which means we'll receive partial results as they become available rather than waiting for all of them to finish generating.

In conclusion, while the requests are not identical in every aspect due to these differences, they still share some common functional aspects that could be considered equivalent under certain conditions and parameters. For instance, both sets of requests should produce outputs with a similar structure if handled correctly by your service's API. However, their specific output will depend on various factors including the model used, temperature setting, streaming status etc.""",
        dimensions=1536,
        encoding_format="base64"
    )

# Chat call
response = client.chat.completions.create(
    model="liquidai_lfm2.5-1.2b-instruct",
    messages=[
        {"role": "system", "content": """Your task is to assign each piece of information (or “memory”) to one or more of the following categories. Feel free to use multiple categories per item when appropriate.\n\n- Personal: family, friends, home, hobbies, lifestyle\n- Relationships: social network, significant others, colleagues\n- Preferences: likes, dislikes, habits, favorite media\n- Health: physical fitness, mental health, diet, sleep\n- Travel: trips, commutes, favorite places, itineraries\n- Work: job roles, companies, projects, promotions\n- Education: courses, degrees, certifications, skills development\n- Projects: to‑dos, milestones, deadlines, status updates\n- AI, ML & Technology: infrastructure, algorithms, tools, research\n- Technical Support: bug reports, error logs, fixes\n- Finance: income, expenses, investments, billing\n- Shopping: purchases, wishlists, returns, deliveries\n- Legal: contracts, policies, regulations, privacy\n- Entertainment: movies, music, games, books, events\n- Messages: emails, SMS, alerts, reminders\n- Customer Support: tickets, inquiries, resolutions\n- Product Feedback: ratings, bug reports, feature requests\n- News: articles, headlines, trending topics\n- Organization: meetings, appointments, calendars\n- Goals: ambitions, KPIs, long‑term objectives\n\nGuidelines:\n- Return ONLY a comma-delimited list of categories (e.g., Personal, Preferences, Work).\n- Do not include any JSON, brackets, quotes, explanations, or additional text.\n- If you cannot categorize the memory, return an empty response.\n- Don't limit yourself to the categories listed above only. Feel free to create new categories based on the memory. Make sure each category is a single concise phrase."""},
        {"role": "user", "content": """Sure! Let's consider an example with a slightly modified endpoint, model and messages.

Endpoint: This is now a GET request to /v1/chat/completions/{id}.

Model: We use the same model as before but this time it's "liquidai_lfm2.5-1.2b-instruct".

Messages (Input): The system and user messages are slightly different, with an additional message from the user asking for a list of programming languages.

Temperature: It is set to 0.5 instead of 0 as before.

Streaming: Streaming is enabled: "stream": true.

Response Format: We demand the same JSON schema output (named "MemoryCategories", strictly enforced, with an array of strings called "categories").

The only difference here compared to your original request is that we're now using a GET method instead of POST and are passing in a chat completion ID.

Impact: The impact on the output will be slightly different due to these changes. With temperature set at 0.5, it might generate more diverse responses than with a lower temperature (like 0). Streaming is enabled which means we'll receive partial results as they become available rather than waiting for all of them to finish generating.

In conclusion, while the requests are not identical in every aspect due to these differences, they still share some common functional aspects that could be considered equivalent under certain conditions and parameters. For instance, both sets of requests should produce outputs with a similar structure if handled correctly by your service's API. However, their specific output will depend on various factors including the model used, temperature setting, streaming status etc."""}
    ],
    temperature=0
)

print(response.choices[0].message.content)