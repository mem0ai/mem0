import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const isLocalDev = process.env.NEXT_PUBLIC_USER_ID ? true : false;

// In local development, we might have dummy values for Supabase
if (!isLocalDev) {
  if (!supabaseUrl) {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL is not set in environment variables.");
  }
  if (!supabaseAnonKey) {
    throw new Error("NEXT_PUBLIC_SUPABASE_ANON_KEY is not set in environment variables.");
  }
}

// Create Supabase client - in local dev, this might use dummy values
export const supabase: SupabaseClient = createClient(
  supabaseUrl || 'http://localhost:8000', // Dummy URL for local dev
  supabaseAnonKey || 'local-dev-anon-key' // Dummy key for local dev
); 