import { env } from './env';
import type {
  SearchRequest,
  SearchResponse,
  FeedbackRequest,
  ErrorReport,
  OutcomeReport,
  FeaturedSchemesResponse,
} from '@/types/api';

export class ApiError extends Error {
  status: number;
  userMessage: string;
  code: string;
  constructor(status: number, userMessage: string, code: string, rawMessage?: string) {
    super(rawMessage ?? userMessage);
    this.status = status;
    this.userMessage = userMessage;
    this.code = code;
  }
}

async function userFacingHttpMessage(resp: Response): Promise<{ message: string; code: string }> {
  const status = resp.status;
  if (status === 429) return { message: 'Too many requests. Please wait a minute and try again.', code: 'rate_limited' };
  if (status === 503) return { message: 'The service is busy or temporarily unavailable. Please try again in a few minutes.', code: 'service_busy' };
  if (status === 422) {
    try {
      const j = (await resp.json()) as { detail?: unknown };
      const d = j.detail;
      if (Array.isArray(d) && d.length) {
        const parts = d.map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: unknown }).msg) : String(x)));
        return { message: `Invalid input: ${parts.join('; ')}`, code: 'invalid_input' };
      }
    } catch {
      // ignore json parse failures — fall through to generic message
    }
    return { message: 'Invalid request. Please shorten or simplify your question.', code: 'invalid_input' };
  }
  return { message: `Something went wrong (HTTP ${status}). Please try again.`, code: 'http_error' };
}

export interface SearchCallResult {
  payload: SearchResponse;
  traceId: string | null;
}

export async function searchSchemes(body: SearchRequest): Promise<SearchCallResult> {
  const resp = await fetch(`${env.BACKEND_URL}/api/search`, {
    method: 'POST',
    signal: AbortSignal.timeout(env.REQUEST_TIMEOUT_MS),
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const { message, code } = await userFacingHttpMessage(resp);
    throw new ApiError(resp.status, message, code);
  }
  const ct = (resp.headers.get('content-type') ?? '').toLowerCase();
  if (!ct.includes('application/json')) {
    throw new ApiError(resp.status, 'Server returned an unexpected response. Please try again.', 'bad_content_type');
  }
  const payload = (await resp.json()) as SearchResponse;
  const traceId = resp.headers.get('X-Trace-Id');
  return { payload, traceId };
}

/** Fire-and-forget. Never throws. */
export function sendFeedback(body: FeedbackRequest): void {
  try {
    void fetch(`${env.BACKEND_URL}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).catch(() => undefined);
  } catch {
    // swallowed
  }
}

/** Fetch the home-grid featured schemes (5 national flagships + state-specific filler).
 * Resolves with the full response or throws an ApiError on non-2xx. */
export async function fetchFeaturedSchemes(
  state: string | null,
  limit = 12,
): Promise<FeaturedSchemesResponse> {
  const params = new URLSearchParams();
  if (state) params.set('state', state);
  params.set('limit', String(limit));
  const resp = await fetch(`${env.BACKEND_URL}/api/v2/featured?${params.toString()}`, {
    method: 'GET',
    signal: AbortSignal.timeout(env.REQUEST_TIMEOUT_MS),
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    const { message, code } = await userFacingHttpMessage(resp);
    throw new ApiError(resp.status, message, code);
  }
  return (await resp.json()) as FeaturedSchemesResponse;
}

/** Fire-and-forget. Never throws. */
export function reportOutcome(body: OutcomeReport): void {
  try {
    void fetch(`${env.BACKEND_URL}/api/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).catch(() => undefined);
  } catch {
    // swallowed
  }
}

/** Fire-and-forget. Never throws. */
export function reportError(body: ErrorReport): void {
  try {
    void fetch(`${env.BACKEND_URL}/api/error`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).catch(() => undefined);
  } catch {
    // swallowed
  }
}

export function mapNetworkErrorToMessage(err: unknown): { message: string; code: string } {
  if (err instanceof ApiError) {
    return { message: err.userMessage, code: err.code };
  }
  if (err instanceof DOMException && err.name === 'TimeoutError') {
    return {
      message: 'The request timed out. The server may be starting up — please try again in a moment.',
      code: 'timeout',
    };
  }
  if (err instanceof SyntaxError) {
    return { message: 'Invalid response from server. Please try again.', code: 'parse_error' };
  }
  if (err instanceof Error && err.message) {
    return { message: err.message, code: 'fetch_failed' };
  }
  return { message: 'Sorry, there was an error connecting to SahayakSetu. Please try again.', code: 'fetch_failed' };
}
