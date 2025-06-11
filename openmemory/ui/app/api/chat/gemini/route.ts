import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import PostHogClient from '@/lib/posthog';

export async function POST(request: NextRequest) {
  try {
    // **SECURITY: Check authentication first**
    const authHeader = request.headers.get('authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { error: 'Unauthorized - Missing or invalid authorization header' },
        { status: 401 }
      );
    }

    const token = authHeader.split(' ')[1];
    
    // Check for local development mode first
    const localUserId = process.env.NEXT_PUBLIC_USER_ID;
    let user;
    
    if (localUserId && token === 'local-dev-token') {
      console.log('Gemini API: Local development mode detected, using local user ID:', localUserId);
      // Create a mock user for local development
      user = {
        id: localUserId,
        email: 'local@example.com',
        app_metadata: { provider: 'local' },
        user_metadata: { name: 'Local User' }
      };
    } else {
      // Normal production flow - verify token with Supabase
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
      
      if (!supabaseUrl || !supabaseAnonKey) {
        console.error('Missing Supabase configuration');
        return NextResponse.json(
          { error: 'Server configuration error' },
          { status: 500 }
        );
      }

      const supabase = createClient(supabaseUrl, supabaseAnonKey);
      const { data: { user: supabaseUser }, error: authError } = await supabase.auth.getUser(token);

      if (authError || !supabaseUser) {
        console.warn('Authentication failed:', authError?.message);
        return NextResponse.json(
          { error: 'Unauthorized - Invalid token' },
          { status: 401 }
        );
      }
      
      user = supabaseUser;
    }

    // **SECURITY: Rate limiting check (basic implementation)**
    // TODO: Implement proper rate limiting with Redis or similar
    console.log(`Gemini API request from user: ${user.id}`);

    const { prompt, memories, selectedMemory } = await request.json();

    // Get Gemini API key from environment variables
    console.log('Checking for GEMINI_API_KEY in environment');
    console.log('Available env keys:', Object.keys(process.env).filter(key => !key.includes('SECRET') && !key.includes('KEY')).join(', '));
    
    // Try multiple possible environment variable names
    const apiKey = process.env.GEMINI_API_KEY || 
                  process.env.NEXT_PUBLIC_GEMINI_API_KEY || 
                  process.env.GOOGLE_API_KEY || 
                  process.env.NEXT_PUBLIC_GOOGLE_API_KEY;
    
    if (!apiKey) {
      console.error('GEMINI_API_KEY not found in environment variables');
      // Create a detailed error message
      const envDebug = {
        hasGeminiKey: !!process.env.GEMINI_API_KEY,
        nodeEnv: process.env.NODE_ENV,
        hasUserID: !!process.env.NEXT_PUBLIC_USER_ID,
        memoryCount: memories?.length || 0
      };
      console.log('Environment debug info:', envDebug);
      
      return NextResponse.json({
        response: `I'm currently unable to access my full capabilities. Debugging info: The server can't find the GEMINI_API_KEY in the environment variables. For now, I can see you have ${memories?.length || 0} memories to analyze.`
      });
    }
    
    console.log('GEMINI_API_KEY found, length:', apiKey.length);

    // Build context with selected memory highlighted
    let contextText = `You are a personal AI assistant with access to the user's memory collection. You have access to ${memories?.length || 0} memories.`;
    
    if (selectedMemory) {
      contextText += `\n\nThe user has specifically asked about this memory:\n`;
      contextText += `Memory ID: ${selectedMemory.id}\n`;
      contextText += `Content: ${selectedMemory.content}\n`;
      contextText += `Created: ${selectedMemory.created_at}\n`;
      contextText += `App/Source: ${selectedMemory.app_name || 'Unknown'}\n`;
      contextText += `Categories: ${selectedMemory.categories?.join(', ') || 'None'}\n`;
      if (selectedMemory.metadata_) {
        contextText += `Additional Details: ${JSON.stringify(selectedMemory.metadata_, null, 2)}\n`;
      }
    }

    contextText += `\n\nOther Memory Context:\n`;
    contextText += memories?.slice(0, 10).map((m: any, index: number) => {
      // Handle different memory formats
      const memoryContent = m.content || m.memory || m.text || 'No content';
      const appName = m.app_name || m.appName || 'unknown app';
      const createdAt = m.created_at || m.createdAt;
      const dateStr = createdAt ? new Date(createdAt).toLocaleDateString() : 'unknown date';
      return `[Memory ${index + 1}] ${memoryContent} (from ${appName} on ${dateStr})`;
    }).join('\n') || 'No other memories available.';

    contextText += `\n\nUser Query: ${prompt}`;
    
    if (selectedMemory) {
      contextText += `\n\nInstructions: Provide a concise response (2-3 paragraphs max) about the selected memory. Focus on key insights and connections. Be direct and avoid repetition.`;
    } else {
      contextText += `\n\nInstructions: Provide a concise, helpful response (2-3 paragraphs max). Be direct and focus on the most relevant insights.`;
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
            text: contextText
          }]
        }],
        generationConfig: {
          maxOutputTokens: 512,  // Reduced from 1024 for more concise responses
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

    // 📊 Track chat interaction with PostHog
    try {
      const posthog = PostHogClient();
      posthog.capture({
        distinctId: user.id,
        event: 'chat_message_sent',
        properties: {
          user_id: user.id,
          user_email: user.email,
          memories_available: memories?.length || 0,
          has_selected_memory: !!selectedMemory,
          selected_memory_app: selectedMemory?.app_name || null,
          prompt_length: prompt.length,
          response_length: generatedText.length,
          model_used: 'gemini-2.0-flash'
        }
      });
      await posthog.shutdown();
    } catch (trackingError) {
      console.error('PostHog tracking failed:', trackingError);
      // Don't let tracking errors break the main functionality
    }

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