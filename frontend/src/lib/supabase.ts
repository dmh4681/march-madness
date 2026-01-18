import { createClient, SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Helper to check if Supabase is configured
export const isSupabaseConfigured = () => {
  return !!(supabaseUrl && supabaseAnonKey);
};

// Create client only if configured, otherwise create a dummy that will fail gracefully
let _supabase: SupabaseClient<Database> | null = null;

export const supabase = (() => {
  if (!_supabase && isSupabaseConfigured()) {
    _supabase = createClient<Database>(supabaseUrl, supabaseAnonKey);
  }
  // Return a proxy that returns empty results if not configured
  if (!_supabase) {
    return {
      from: () => ({
        select: () => ({
          eq: () => ({
            order: () => ({
              limit: () => ({
                single: () => Promise.resolve({ data: null, error: 'Not configured' }),
              }),
            }),
            single: () => Promise.resolve({ data: null, error: 'Not configured' }),
          }),
          order: () => ({
            limit: () => Promise.resolve({ data: [], error: null }),
          }),
        }),
      }),
    } as unknown as SupabaseClient<Database>;
  }
  return _supabase;
})();
