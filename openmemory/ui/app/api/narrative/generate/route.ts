import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { generateNarrativeWithGemini } from '@/lib/gemini';

export async function POST(req: NextRequest) {
    try {
        // Authenticate the request
        const authHeader = req.headers.get('authorization');
        if (!authHeader) {
            return NextResponse.json({ detail: 'Authorization header is missing' }, { status: 401 });
        }

        // Extract memories from the request body
        const { memories } = await req.json();

        if (!memories || !Array.isArray(memories) || memories.length === 0) {
            return NextResponse.json({ detail: 'No memories provided to generate a narrative.' }, { status: 400 });
        }

        // Format the memories into a text context
        const memoryContext = memories.map((m: any, index: number) => {
            const content = m.content || m.text || 'No content';
            const date = m.created_at ? new Date(m.created_at).toLocaleDateString() : 'an unknown date';
            const source = m.app_name || 'an unknown source';
            return `Memory ${index + 1} (from ${source} on ${date}): ${content}`;
        }).join('\\n\\n');
        
        // Generate the narrative using the context
        const narrative = await generateNarrativeWithGemini(memoryContext);

        return NextResponse.json({ narrative });

    } catch (error: any) {
        console.error("Error in narrative generation route:", error);
        return NextResponse.json({ detail: error.message }, { status: 500 });
    }
} 