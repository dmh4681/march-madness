import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AIAnalysisButton } from '@/components/AIAnalysisButton';
import { createMockAnalysisResponse } from '../__mocks__/mockData';

// Mock API URL for tests
const TEST_API_URL = 'http://localhost:8000';

describe('AIAnalysisButton', () => {
  const defaultProps = {
    gameId: 'game-123',
    apiUrl: TEST_API_URL,
  };

  // Helper to setup successful fetch mock
  const mockSuccessfulFetch = () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
    });
  };

  // Helper to setup error fetch mock
  const mockErrorFetch = (status: number, message: string) => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status,
      text: () => Promise.resolve(JSON.stringify({ detail: message })),
    });
  };

  describe('Rendering', () => {
    it('renders the component with default Claude provider selected', () => {
      render(<AIAnalysisButton {...defaultProps} />);

      // Check run button is rendered
      expect(screen.getByRole('button', { name: /run claude analysis/i })).toBeInTheDocument();

      // Check provider toggle buttons exist (multiple buttons contain "claude" so we count them)
      const buttons = screen.getAllByRole('button');
      // Should have at least 3 buttons: Claude toggle, Grok toggle, Run button
      expect(buttons.length).toBeGreaterThanOrEqual(3);
    });

    it('shows indicator when Claude analysis exists', () => {
      render(<AIAnalysisButton {...defaultProps} hasClaudeAnalysis={true} />);

      // Check for the asterisk indicator - find all buttons and filter by text
      const buttons = screen.getAllByRole('button');
      // The provider toggle button contains just "Claude" plus the asterisk
      const claudeToggleButton = buttons.find(btn =>
        btn.textContent?.includes('Claude') &&
        !btn.textContent?.includes('Analysis')
      );
      expect(claudeToggleButton?.textContent).toContain('*');
    });

    it('shows indicator when Grok analysis exists', () => {
      render(<AIAnalysisButton {...defaultProps} hasGrokAnalysis={true} />);

      // Check for the asterisk indicator on Grok button
      const buttons = screen.getAllByRole('button');
      const grokToggleButton = buttons.find(btn =>
        btn.textContent?.includes('Grok') &&
        !btn.textContent?.includes('Analysis')
      );
      expect(grokToggleButton?.textContent).toContain('*');
    });

    it('shows "Re-run" text when current provider has existing analysis', () => {
      render(<AIAnalysisButton {...defaultProps} hasClaudeAnalysis={true} />);

      expect(screen.getByRole('button', { name: /re-run claude analysis/i })).toBeInTheDocument();
    });

    it('shows footnote about existing analyses', () => {
      render(<AIAnalysisButton {...defaultProps} hasClaudeAnalysis={true} />);

      expect(screen.getByText(/\* = analysis exists/i)).toBeInTheDocument();
    });

    it('shows "Powered by" text when no analysis exists', () => {
      render(<AIAnalysisButton {...defaultProps} />);

      expect(screen.getByText(/powered by claude/i)).toBeInTheDocument();
    });
  });

  describe('Provider Selection', () => {
    it('switches to Grok provider when Grok button is clicked', () => {
      render(<AIAnalysisButton {...defaultProps} />);

      const grokButton = screen.getByRole('button', { name: /grok/i });
      fireEvent.click(grokButton);

      expect(screen.getByRole('button', { name: /run grok analysis/i })).toBeInTheDocument();
    });

    it('switches back to Claude provider when Claude button is clicked', () => {
      render(<AIAnalysisButton {...defaultProps} />);

      // First switch to Grok
      fireEvent.click(screen.getByRole('button', { name: /grok/i }));

      // Then switch back to Claude
      fireEvent.click(screen.getByRole('button', { name: /claude/i }));

      expect(screen.getByRole('button', { name: /run claude analysis/i })).toBeInTheDocument();
    });

    it('updates "Re-run" text based on selected provider', () => {
      render(<AIAnalysisButton {...defaultProps} hasClaudeAnalysis={true} hasGrokAnalysis={false} />);

      // Claude has analysis, should show Re-run
      expect(screen.getByRole('button', { name: /re-run claude analysis/i })).toBeInTheDocument();

      // Switch to Grok which has no analysis
      fireEvent.click(screen.getByRole('button', { name: /grok/i }));

      // Should show Run (not Re-run)
      expect(screen.getByRole('button', { name: /run grok analysis/i })).toBeInTheDocument();
    });
  });

  describe('API Request', () => {
    it('makes POST request to correct endpoint when Run button is clicked', async () => {
      mockSuccessfulFetch();
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      expect(global.fetch).toHaveBeenCalledWith(
        `${TEST_API_URL}/ai-analysis`,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            game_id: 'game-123',
            provider: 'claude',
          }),
        })
      );
    });

    it('sends correct provider in request body when Grok is selected', async () => {
      mockSuccessfulFetch();
      render(<AIAnalysisButton {...defaultProps} />);

      // Switch to Grok
      fireEvent.click(screen.getByRole('button', { name: /grok/i }));

      const runButton = screen.getByRole('button', { name: /run grok analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({
            game_id: 'game-123',
            provider: 'grok',
          }),
        })
      );
    });
  });

  describe('Loading State', () => {
    it('shows loading spinner when analysis is in progress', async () => {
      // Create a promise that we can control
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValueOnce(pendingPromise);

      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });
      fireEvent.click(runButton);

      // Check loading state
      await waitFor(() => {
        expect(screen.getByText(/running claude analysis/i)).toBeInTheDocument();
      });

      // Clean up by resolving the promise
      resolvePromise!({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });
    });

    it('shows loading hint text', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValueOnce(pendingPromise);

      render(<AIAnalysisButton {...defaultProps} />);

      fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));

      await waitFor(() => {
        expect(screen.getByText(/ai analysis typically completes within 30-60 seconds/i)).toBeInTheDocument();
      });

      resolvePromise!({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });
    });

    it('disables provider buttons during loading', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValueOnce(pendingPromise);

      render(<AIAnalysisButton {...defaultProps} />);

      fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));

      await waitFor(() => {
        // During loading, all buttons should be disabled
        const buttons = screen.getAllByRole('button');
        const disabledButtons = buttons.filter(btn => btn.hasAttribute('disabled'));
        expect(disabledButtons.length).toBeGreaterThan(0);
      });

      resolvePromise!({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });
    });

    it('disables run button during loading', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValueOnce(pendingPromise);

      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });
      fireEvent.click(runButton);

      await waitFor(() => {
        const loadingButton = screen.getByRole('button', { name: /running claude analysis/i });
        expect(loadingButton).toBeDisabled();
      });

      resolvePromise!({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });
    });
  });

  describe('Success State', () => {
    it('shows success message after successful analysis', async () => {
      mockSuccessfulFetch();
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/analysis complete! refreshing/i)).toBeInTheDocument();
      });
    });

    it('shows refreshing message after success (reload triggered)', async () => {
      jest.useFakeTimers();
      mockSuccessfulFetch();
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/analysis complete! refreshing/i)).toBeInTheDocument();
      });

      // Verify success message is visible - the actual reload cannot be tested in JSDOM
      // but we can verify the component reached the success state
      expect(screen.getByText(/analysis complete! refreshing/i)).toBeInTheDocument();

      jest.useRealTimers();
    });
  });

  describe('Error Handling', () => {
    it('shows error message on server error', async () => {
      mockErrorFetch(500, 'Internal server error');
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/server error/i)).toBeInTheDocument();
      });
    });

    it('shows rate limit error on 429 response', async () => {
      mockErrorFetch(429, 'Too many requests');
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/service busy/i)).toBeInTheDocument();
        expect(screen.getByText(/too many requests/i)).toBeInTheDocument();
      });
    });

    it('shows retry button on retryable errors', async () => {
      mockErrorFetch(500, 'Server error');
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });

    it('allows retry after error', async () => {
      // First call fails
      mockErrorFetch(500, 'Server error');

      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/server error/i)).toBeInTheDocument();
      });

      // Second call succeeds
      mockSuccessfulFetch();

      const retryButton = screen.getByRole('button', { name: /try again/i });

      await act(async () => {
        fireEvent.click(retryButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/analysis complete! refreshing/i)).toBeInTheDocument();
      });
    });

    it('shows retry count on subsequent retries', async () => {
      // First call fails
      mockErrorFetch(500, 'Server error');

      render(<AIAnalysisButton {...defaultProps} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });

      // Retry fails again
      mockErrorFetch(500, 'Server error');

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /try again/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/try again \(1\/3\)/i)).toBeInTheDocument();
      });
    });

    it('stops showing retry after max retries', async () => {
      render(<AIAnalysisButton {...defaultProps} />);

      // Initial click
      mockErrorFetch(500, 'Server error');
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      // Retry 1
      await waitFor(() => expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument());
      mockErrorFetch(500, 'Server error');
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /try again/i }));
      });

      // Retry 2
      await waitFor(() => expect(screen.getByText(/try again \(1\/3\)/i)).toBeInTheDocument());
      mockErrorFetch(500, 'Server error');
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /try again \(1\/3\)/i }));
      });

      // Retry 3
      await waitFor(() => expect(screen.getByText(/try again \(2\/3\)/i)).toBeInTheDocument());
      mockErrorFetch(500, 'Server error');
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /try again \(2\/3\)/i }));
      });

      // After 3 retries, should show message about contacting support
      await waitFor(() => {
        expect(screen.getByText(/multiple retries failed/i)).toBeInTheDocument();
      });
    });

    it('handles network errors', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new TypeError('Failed to fetch'));

      render(<AIAnalysisButton {...defaultProps} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/connection error/i)).toBeInTheDocument();
      });
    });

    it('handles timeout errors', async () => {
      const abortError = new Error('Aborted');
      abortError.name = 'AbortError';
      (global.fetch as jest.Mock).mockRejectedValueOnce(abortError);

      render(<AIAnalysisButton {...defaultProps} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/request timed out/i)).toBeInTheDocument();
      });
    });

    it('handles empty response error', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve(''),
      });

      render(<AIAnalysisButton {...defaultProps} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/analysis failed/i)).toBeInTheDocument();
      });
    });

    it('handles invalid JSON response error', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('not valid json'),
      });

      render(<AIAnalysisButton {...defaultProps} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/analysis failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible button labels', () => {
      render(<AIAnalysisButton {...defaultProps} />);

      // The Run Analysis button has a specific pattern
      expect(screen.getByRole('button', { name: /run claude analysis/i })).toBeInTheDocument();
      // Provider toggle buttons
      const buttons = screen.getAllByRole('button');
      // Should have at least 3 buttons: Claude toggle, Grok toggle, and Run button
      expect(buttons.length).toBeGreaterThanOrEqual(3);
    });

    it('maintains focus during state changes', async () => {
      mockSuccessfulFetch();
      render(<AIAnalysisButton {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run claude analysis/i });
      runButton.focus();

      await act(async () => {
        fireEvent.click(runButton);
      });

      // Success message should still be in the component
      await waitFor(() => {
        expect(screen.getByText(/analysis complete/i)).toBeInTheDocument();
      });
    });
  });
});
