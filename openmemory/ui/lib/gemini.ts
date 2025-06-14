// This function calls the Gemini API
export async function generateNarrativeWithGemini(context: string) {
    const geminiApiKey = process.env.GEMINI_API_KEY;
    if (!geminiApiKey) {
        throw new Error("GEMINI_API_KEY environment variable is not set in the Next.js environment.");
    }

    const systemPrompt = `You are an expert biographer and data analyst. Your task is to synthesize a user's memories into a factual, professional, and insightful summary.

**Output Guidelines:**
- **Perspective:** Write in the third-person ("They are...", "Their work focuses on..."). Do NOT use "I" or "my".
- **Tone:** Maintain a professional, objective, and factual tone. Avoid speculation, "cheesy" phrasing, or overly poetic language.
- **Content:** Extract and present concrete, factual information. If the data is available, touch upon:
    - Their core values and personality traits.
    - Their professional background and key projects/milestones.
    - Their recent focus and activities.
- **Structure:** Use the following markdown headings:
    - ## Professional Summary
    - ## Core Values & Personality
    - ## Key Projects & Recent Activity
- **Length:** The entire summary should be concise and easily digestible.

Based on the following data, create the user summary.

DATA:
${context}`;

    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-06-05:generateContent?key=${geminiApiKey}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            contents: [{
                parts: [{ text: systemPrompt }]
            }],
            generationConfig: {
                temperature: 0.5, // Lower temperature for more factual output
                maxOutputTokens: 8192,
            }
        })
    });

    if (!response.ok) {
        const errorBody = await response.text();
        console.error(`Gemini API failed with status ${response.status}:`, errorBody);
        throw new Error('Failed to generate narrative with Gemini.');
    }

    const data = await response.json();

    // Handle cases where the response is blocked due to safety settings or other issues.
    if (!data.candidates) {
        if (data.promptFeedback) {
            console.error("Gemini API request was blocked. Feedback:", JSON.stringify(data.promptFeedback, null, 2));
            const blockReason = data.promptFeedback.blockReason || 'Unknown';
            throw new Error(`The request was blocked by the AI for safety reasons (${blockReason}). Please review the content.`);
        } else {
            console.error("Invalid response structure from Gemini API (no candidates):", data);
            throw new Error("Received an invalid response from the AI. The response did not contain any candidates.");
        }
    }
    
    // It's possible for a candidate to exist but have no content if generation is stopped.
    if (!data.candidates[0].content || !data.candidates[0].content.parts || !data.candidates[0].content.parts[0]) {
        const finishReason = data.candidates[0].finishReason;
        const safetyRatings = data.candidates[0].safetyRatings;
        
        if (finishReason) {
             console.error(`Gemini generation finished early. Reason: ${finishReason}`, safetyRatings ? `Ratings: ${JSON.stringify(safetyRatings)}` : '');
             throw new Error(`AI generation was stopped. Reason: ${finishReason}.`);
        } else {
            console.error("Invalid response structure from Gemini API (malformed candidate):", data);
            throw new Error("Received an invalid response from the AI. Please try again.");
        }
    }
    
    return data.candidates[0].content.parts[0].text;
} 