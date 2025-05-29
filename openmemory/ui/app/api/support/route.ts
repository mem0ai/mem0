/**
 * Support form API endpoint
 * 
 * Environment Variables Required:
 * - RESEND_API_KEY: Your Resend API key for sending emails
 * 
 * If RESEND_API_KEY is not configured, the form will still work
 * but support requests will be logged to console for manual processing.
 */

import { NextRequest, NextResponse } from 'next/server';
import { Resend } from 'resend';

const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(request: NextRequest) {
  try {
    const { name, email, message } = await request.json();

    if (!name || !email || !message) {
      return NextResponse.json(
        { error: 'All fields are required' },
        { status: 400 }
      );
    }

    // Check if Resend is configured
    if (!process.env.RESEND_API_KEY) {
      console.warn('RESEND_API_KEY not configured, logging support request instead');
      console.log('Support request:', { name, email, message });
      
      // Still return success for the user
      return NextResponse.json(
        { message: 'Support request received (logged for manual processing)' },
        { status: 200 }
      );
    }

    try {
      const data = await resend.emails.send({
        from: 'Jean Memory Support <support@jeanmemory.com>',
        to: ['jonathan@jeantechnologies.com'],
        replyTo: email,
        subject: `Jean Memory Support Request from ${name}`,
        html: `
          <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #8b5cf6;">New Jean Memory Support Request</h2>
            
            <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
              <p><strong>Name:</strong> ${name}</p>
              <p><strong>Email:</strong> ${email}</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
              <h3>Message:</h3>
              <p style="white-space: pre-wrap;">${message}</p>
            </div>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
            
            <p style="color: #6b7280; font-size: 14px;">
              <em>Sent from Jean Memory MCP Setup Page</em><br>
              <em>Reply to this email to respond directly to ${name}</em>
            </p>
          </div>
        `
      });

      console.log('Email sent successfully:', data);

      return NextResponse.json(
        { message: 'Support request sent successfully' },
        { status: 200 }
      );

    } catch (emailError) {
      console.error('Resend error:', emailError);
      
      // Log the request for manual processing
      console.log('Fallback: logging support request for manual processing', { name, email, message });
      
      return NextResponse.json(
        { message: 'Support request received (will be processed manually)' },
        { status: 200 }
      );
    }

  } catch (error) {
    console.error('Error processing support request:', error);
    return NextResponse.json(
      { error: 'Failed to process support request' },
      { status: 500 }
    );
  }
} 