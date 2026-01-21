-- =============================================================================
-- Fix Sports Betting RLS Policies
-- Created: 2026-01-21
-- Purpose: Fix RLS policies that were incorrectly applied to ai_analysis table
-- =============================================================================

-- The previous security migration put ai_analysis in the agent_tables array,
-- which gave it a restrictive "service_role only" policy. This broke the
-- sports betting API since ai_analysis needs to be publicly readable.

-- =============================================================================
-- FIX AI_ANALYSIS TABLE
-- =============================================================================

-- Drop the restrictive policy
DROP POLICY IF EXISTS "Service role only access" ON ai_analysis;
DROP POLICY IF EXISTS "Users can view own data" ON ai_analysis;
DROP POLICY IF EXISTS "Users can insert own data" ON ai_analysis;
DROP POLICY IF EXISTS "Service role full access" ON ai_analysis;

-- Create correct policies for sports betting use case:
-- - Public can READ analysis results
-- - Only service role can INSERT/UPDATE (backend creates analyses)

CREATE POLICY "Public read access" ON ai_analysis
  FOR SELECT USING (true);

CREATE POLICY "Service role can insert" ON ai_analysis
  FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can update" ON ai_analysis
  FOR UPDATE USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can delete" ON ai_analysis
  FOR DELETE USING (auth.role() = 'service_role');

-- =============================================================================
-- VERIFY OTHER SPORTS BETTING TABLES HAVE CORRECT POLICIES
-- =============================================================================

-- These should already have "Public read access" from the previous migration,
-- but let's ensure the service role can also write (for data refresh operations)

-- teams table
DROP POLICY IF EXISTS "Service role write access" ON teams;
CREATE POLICY "Service role write access" ON teams
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- games table
DROP POLICY IF EXISTS "Service role write access" ON games;
CREATE POLICY "Service role write access" ON games
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- spreads table
DROP POLICY IF EXISTS "Service role write access" ON spreads;
CREATE POLICY "Service role write access" ON spreads
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- rankings table
DROP POLICY IF EXISTS "Service role write access" ON rankings;
CREATE POLICY "Service role write access" ON rankings
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- predictions table
DROP POLICY IF EXISTS "Service role write access" ON predictions;
CREATE POLICY "Service role write access" ON predictions
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- bet_results table
DROP POLICY IF EXISTS "Service role write access" ON bet_results;
CREATE POLICY "Service role write access" ON bet_results
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- kenpom_ratings table
DROP POLICY IF EXISTS "Service role write access" ON kenpom_ratings;
CREATE POLICY "Service role write access" ON kenpom_ratings
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- haslametrics_ratings table
DROP POLICY IF EXISTS "Service role write access" ON haslametrics_ratings;
CREATE POLICY "Service role write access" ON haslametrics_ratings
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON POLICY "Public read access" ON ai_analysis IS 'Allow anyone to read AI analyses (public betting insights)';
COMMENT ON POLICY "Service role can insert" ON ai_analysis IS 'Only backend service can create new analyses';
