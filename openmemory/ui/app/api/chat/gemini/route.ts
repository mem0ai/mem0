import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { prompt, memories } = await request.json();

    // Get Gemini API key from environment variables
    const apiKey = process.env.GEMINI_API_KEY;
    
    if (!apiKey) {
      console.warn('GEMINI_API_KEY not found in environment variables');
      return NextResponse.json({
        response: `I'm currently unable to access my full capabilities. To enable Gemini AI integration, please add your GEMINI_API_KEY to the environment variables. For now, I can see you have ${memories?.length || 0} memories to analyze.`
      });
    }

    // Updated to use the latest stable Gemini 2.0 Flash model
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [{
          parts: [{
            text: `You are a personal AI assistant with access to the user's memory collection. You have access to ${memories?.length || 0} memories.

Memory Context:
${memories?.slice(0, 10).map((m: any, index: number) => 
  `[Memory ${index + 1}] ${m.content} (from ${m.app_name || 'unknown app'})`
).join('\n') || 'No memories available.'}

User Query: ${prompt}

Please provide a helpful response based on the available memory context.`
          }]
        }],
        generationConfig: {
          maxOutputTokens: 1024,
          temperature: 0.7,
        },
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error(`Gemini API error: ${response.status}`, errorData);
      throw new Error(`Gemini API error: ${response.status} - ${errorData}`);
    }

    const data = await response.json();
    const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text || 'Sorry, I could not generate a response.';

    return NextResponse.json({
      response: generatedText
    });

  } catch (error) {
    console.error('Gemini API error:', error);
    return NextResponse.json({
      response: "I'm experiencing some technical difficulties right now. Please try again later.",
      error: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
} 