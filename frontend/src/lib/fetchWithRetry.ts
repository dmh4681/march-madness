/**
 * Fetch with Retry + Error Categorization
 *
 * Wraps the browser fetch() API with:
 * - Configurable timeout via AbortController
 * - Exponential backoff retry on transient errors
 * - User-friendly error categorization
 */

export type ErrorCategory = 'network' | 'timeout' | 'server' | 'auth' | 'unknown';

export interface CategorizedError {
  category: ErrorCategory;
  /** User-facing message */
  message: string;
  /** Technical detail for console logging */
  technical: string;
  retryable: boolean;
}

export interface FetchRetryOptions {
  /** Maximum retry attempts (default: 3) */
  maxRetries?: number;
  /** Base delay in ms for first retry (default: 1000) */
  baseDelayMs?: number;
  /** Request timeout in ms (default: 10000) */
  timeoutMs?: number;
}

const DEFAULT_OPTIONS: Required<FetchRetryOptions> = {
  maxRetries: 3,
  baseDelayMs: 1000,
  timeoutMs: 10000,
};

/** HTTP status codes safe to retry */
const RETRYABLE_STATUS_CODES = new Set([429, 500, 502, 503, 504]);

/**
 * Categorize an error for user-friendly messaging.
 */
export function categorizeError(error: unknown, statusCode?: number): CategorizedError {
  // Timeout (AbortController signal)
  if (error instanceof DOMException && error.name === 'AbortError') {
    return {
      category: 'timeout',
      message: 'Request timed out. The server may be busy.',
      technical: 'Request aborted due to timeout',
      retryable: true,
    };
  }

  // Network errors (no response received)
  if (error instanceof TypeError) {
    return {
      category: 'network',
      message: 'Unable to connect. Check your internet connection.',
      technical: error.message,
      retryable: true,
    };
  }

  // HTTP status-based categorization
  if (statusCode) {
    if (statusCode === 401 || statusCode === 403) {
      return {
        category: 'auth',
        message: 'Authentication error. Please refresh the page.',
        technical: `HTTP ${statusCode}`,
        retryable: false,
      };
    }
    if (statusCode === 429) {
      return {
        category: 'server',
        message: 'Too many requests. Please wait a moment.',
        technical: 'Rate limited (429)',
        retryable: true,
      };
    }
    if (statusCode >= 500) {
      return {
        category: 'server',
        message: 'Server error. Our systems are experiencing issues.',
        technical: `HTTP ${statusCode}`,
        retryable: true,
      };
    }
  }

  return {
    category: 'unknown',
    message: 'Something went wrong. Please try again.',
    technical: error instanceof Error ? error.message : String(error),
    retryable: true,
  };
}

/**
 * Fetch with retry, timeout, and error categorization.
 *
 * Retries on: network errors, timeouts, 5xx, 429.
 * Does NOT retry on: 4xx (except 429).
 * Throws the final error if all retries are exhausted.
 */
export async function fetchWithRetry(
  url: string,
  init?: RequestInit,
  options?: FetchRetryOptions
): Promise<Response> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  let lastError: unknown;

  for (let attempt = 0; attempt <= opts.maxRetries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), opts.timeoutMs);

    try {
      const response = await fetch(url, {
        ...init,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Retry on server errors if attempts remain
      if (RETRYABLE_STATUS_CODES.has(response.status) && attempt < opts.maxRetries) {
        const delay = opts.baseDelayMs * Math.pow(2, attempt);
        console.warn(
          `[fetchWithRetry] HTTP ${response.status} from ${url}, retrying in ${delay}ms (${attempt + 1}/${opts.maxRetries})`
        );
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }

      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      lastError = error;

      const categorized = categorizeError(error);

      if (!categorized.retryable || attempt >= opts.maxRetries) {
        throw error;
      }

      const delay = opts.baseDelayMs * Math.pow(2, attempt);
      console.warn(
        `[fetchWithRetry] ${categorized.technical}, retrying in ${delay}ms (${attempt + 1}/${opts.maxRetries})`
      );
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  throw lastError;
}
