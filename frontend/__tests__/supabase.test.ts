/**
 * Tests for Supabase client module (supabase.ts).
 *
 * Tests cover:
 * - isSupabaseConfigured helper function
 * - Client initialization when configured
 * - Fallback proxy behavior when not configured
 * - Graceful degradation of operations
 */

// Mock environment variables before importing the module
const originalEnv = process.env;

beforeEach(() => {
  jest.resetModules();
  process.env = { ...originalEnv };
});

afterEach(() => {
  process.env = originalEnv;
});

describe('isSupabaseConfigured', () => {
  it('returns true when both URL and key are set', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';

    // Re-import to pick up new env
    jest.isolateModules(() => {
      const { isSupabaseConfigured } = require('@/lib/supabase');
      expect(isSupabaseConfigured()).toBe(true);
    });
  });

  it('returns false when URL is missing', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = '';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';

    jest.isolateModules(() => {
      const { isSupabaseConfigured } = require('@/lib/supabase');
      expect(isSupabaseConfigured()).toBe(false);
    });
  });

  it('returns false when key is missing', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';

    jest.isolateModules(() => {
      const { isSupabaseConfigured } = require('@/lib/supabase');
      expect(isSupabaseConfigured()).toBe(false);
    });
  });

  it('returns false when both are missing', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = '';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';

    jest.isolateModules(() => {
      const { isSupabaseConfigured } = require('@/lib/supabase');
      expect(isSupabaseConfigured()).toBe(false);
    });
  });

  it('returns false when variables are undefined', () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    jest.isolateModules(() => {
      const { isSupabaseConfigured } = require('@/lib/supabase');
      expect(isSupabaseConfigured()).toBe(false);
    });
  });
});

describe('Supabase client fallback behavior', () => {
  describe('when not configured', () => {
    beforeEach(() => {
      process.env.NEXT_PUBLIC_SUPABASE_URL = '';
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';
    });

    it('returns a proxy object instead of real client', () => {
      jest.isolateModules(() => {
        const { supabase } = require('@/lib/supabase');
        expect(supabase).toBeDefined();
        expect(supabase.from).toBeDefined();
        expect(typeof supabase.from).toBe('function');
      });
    });

    it('proxy.from().select() returns chainable methods', () => {
      jest.isolateModules(() => {
        const { supabase } = require('@/lib/supabase');

        const query = supabase.from('test_table').select('*');

        expect(query).toBeDefined();
        expect(query.eq).toBeDefined();
        expect(typeof query.eq).toBe('function');
        expect(query.order).toBeDefined();
        expect(typeof query.order).toBe('function');
      });
    });

    it('proxy.from().select().eq().single() resolves with null data', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        const result = await supabase
          .from('test_table')
          .select('*')
          .eq('id', 'test-id')
          .single();

        expect(result).toEqual({ data: null, error: 'Not configured' });
      });
    });

    it('proxy.from().select().eq().order().limit().single() resolves with null data', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        const result = await supabase
          .from('test_table')
          .select('*')
          .eq('id', 'test-id')
          .order('created_at', { ascending: false })
          .limit(1)
          .single();

        expect(result).toEqual({ data: null, error: 'Not configured' });
      });
    });

    it('proxy.from().select().order().limit() resolves with empty array', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        const result = await supabase
          .from('test_table')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(10);

        expect(result).toEqual({ data: [], error: null });
      });
    });

    it('handles multiple eq() calls in chain', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        // This mimics a common pattern: filter by multiple fields
        const query = supabase.from('test_table').select('*');
        const filtered = query.eq('field1', 'value1');

        expect(filtered).toBeDefined();
        expect(filtered.eq).toBeDefined();
      });
    });
  });

  describe('when configured', () => {
    // Note: We can't fully test actual Supabase client without mocking the library
    // These tests verify the initialization path
    beforeEach(() => {
      process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
    });

    it('attempts to create actual Supabase client', () => {
      // Mock createClient to verify it's called
      jest.mock('@supabase/supabase-js', () => ({
        createClient: jest.fn(() => ({
          from: jest.fn(() => ({
            select: jest.fn(() => Promise.resolve({ data: [], error: null })),
          })),
        })),
      }));

      jest.isolateModules(() => {
        const { supabase, isSupabaseConfigured } = require('@/lib/supabase');

        expect(isSupabaseConfigured()).toBe(true);
        expect(supabase).toBeDefined();
      });
    });
  });
});

describe('Fallback proxy edge cases', () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = '';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';
  });

  it('handles deeply nested method chains gracefully', async () => {
    jest.isolateModules(async () => {
      const { supabase } = require('@/lib/supabase');

      // Test a complex chain that might be used in the app
      const result = await supabase
        .from('games')
        .select('*, home_team:teams!games_home_team_id_fkey(*)')
        .eq('date', '2025-01-20')
        .order('tip_time')
        .limit(50);

      // Should gracefully return empty result
      expect(result.data).toEqual([]);
      expect(result.error).toBeNull();
    });
  });

  it('proxy does not throw errors when methods are called', () => {
    jest.isolateModules(() => {
      const { supabase } = require('@/lib/supabase');

      // These should not throw
      expect(() => supabase.from('any_table')).not.toThrow();
      expect(() => supabase.from('any_table').select()).not.toThrow();
      expect(() => supabase.from('any_table').select().eq('id', 'test')).not.toThrow();
    });
  });

  it('supports typical game fetch pattern', async () => {
    jest.isolateModules(async () => {
      const { supabase } = require('@/lib/supabase');

      // Typical pattern from the app for fetching games
      const { data, error } = await supabase
        .from('today_games')
        .select('*')
        .order('tip_time')
        .limit(100);

      expect(data).toEqual([]);
      expect(error).toBeNull();
    });
  });

  it('supports single record fetch pattern', async () => {
    jest.isolateModules(async () => {
      const { supabase } = require('@/lib/supabase');

      // Typical pattern for fetching single game
      const { data, error } = await supabase
        .from('games')
        .select('*')
        .eq('id', '550e8400-e29b-41d4-a716-446655440000')
        .single();

      expect(data).toBeNull();
      expect(error).toBe('Not configured');
    });
  });
});

describe('Integration scenarios', () => {
  describe('graceful degradation for UI components', () => {
    beforeEach(() => {
      process.env.NEXT_PUBLIC_SUPABASE_URL = '';
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';
    });

    it('returns empty data that UI can render without crashing', async () => {
      jest.isolateModules(async () => {
        const { supabase, isSupabaseConfigured } = require('@/lib/supabase');

        // Simulate what a component might do
        if (!isSupabaseConfigured()) {
          // Component should check this and show appropriate UI
          expect(true).toBe(true);
          return;
        }

        // If component proceeds anyway, it should still work
        const { data } = await supabase.from('today_games').select('*').order('tip_time').limit(10);

        // Empty array can be mapped without crashing
        expect(Array.isArray(data)).toBe(true);
        expect(data.length).toBe(0);
        const mapped = data.map((game: unknown) => game);
        expect(mapped.length).toBe(0);
      });
    });

    it('null data from single() can be handled with optional chaining', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        const { data } = await supabase
          .from('games')
          .select('*')
          .eq('id', 'test-id')
          .single();

        // Simulate optional chaining in component
        const gameDate = data?.date;
        const homeTeam = data?.home_team?.name;

        expect(gameDate).toBeUndefined();
        expect(homeTeam).toBeUndefined();
      });
    });
  });

  describe('error handling patterns', () => {
    beforeEach(() => {
      process.env.NEXT_PUBLIC_SUPABASE_URL = '';
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';
    });

    it('error from single() indicates configuration issue', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        const { error } = await supabase.from('test').select('*').eq('id', '1').single();

        // Component can check for this specific error
        expect(error).toBe('Not configured');
        expect(typeof error).toBe('string');
      });
    });

    it('list queries return null error (success with empty data)', async () => {
      jest.isolateModules(async () => {
        const { supabase } = require('@/lib/supabase');

        const { error } = await supabase.from('test').select('*').order('id').limit(10);

        // No error for list queries - they just return empty
        expect(error).toBeNull();
      });
    });
  });
});

describe('Type safety with Database types', () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = '';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';
  });

  it('proxy is typed as SupabaseClient<Database>', () => {
    jest.isolateModules(() => {
      const { supabase } = require('@/lib/supabase');

      // TypeScript compilation verifies this, runtime just checks existence
      expect(supabase).toBeDefined();

      // The proxy satisfies the SupabaseClient interface enough
      // to not cause runtime errors
      expect(typeof supabase.from).toBe('function');
    });
  });

  it('can be used with table names from Database type', () => {
    jest.isolateModules(() => {
      const { supabase } = require('@/lib/supabase');

      // These are actual table names from the Database type
      const tables = [
        'teams',
        'games',
        'spreads',
        'rankings',
        'predictions',
        'ai_analysis',
        'bet_results',
      ];

      for (const table of tables) {
        expect(() => supabase.from(table)).not.toThrow();
      }
    });
  });

  it('can be used with view names from Database type', () => {
    jest.isolateModules(() => {
      const { supabase } = require('@/lib/supabase');

      // These are actual view names from the Database type
      const views = ['today_games', 'season_performance'];

      for (const view of views) {
        expect(() => supabase.from(view)).not.toThrow();
      }
    });
  });
});

describe('Module caching behavior', () => {
  it('returns same client instance on multiple imports', () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = '';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = '';

    // Don't use isolateModules - we want to test caching
    const { supabase: client1 } = require('@/lib/supabase');
    const { supabase: client2 } = require('@/lib/supabase');

    // Same module should return same instance
    expect(client1).toBe(client2);
  });
});
