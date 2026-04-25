const viteEnv = import.meta.env;

function resolveBackendUrl(): string {
  const explicit = viteEnv.VITE_BACKEND_URL;
  if (typeof explicit === 'string' && explicit.trim()) return explicit.trim();
  if (typeof window === 'undefined') return 'http://localhost:8000';
  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') return 'http://localhost:8000';
  // Last-resort prod fallback. Always prefer setting VITE_BACKEND_URL in Vercel —
  // hardcoding here was the cause of the "FE still hitting old Render URL" bug.
  return 'https://sahayak-setu-production.up.railway.app';
}

function flagEnabled(v: unknown, defaultValue: boolean): boolean {
  if (v === undefined || v === null || v === '') return defaultValue;
  return String(v).toLowerCase() !== 'false' && String(v) !== '0';
}

export const env = {
  BACKEND_URL: resolveBackendUrl(),
  VAPI_PUBLIC_KEY: viteEnv.VITE_VAPI_PUBLIC_KEY ?? '',
  VAPI_ASSISTANT_ID: viteEnv.VITE_VAPI_ASSISTANT_ID ?? '',
  /** Set VITE_VAPI_ENABLED=false to skip Vapi entirely (browser SpeechRecognition only). */
  VAPI_ENABLED: flagEnabled(viteEnv.VITE_VAPI_ENABLED, true),
  SESSION_USER_ID_KEY: 'sahayak_session_user_id',
  LAST_QUERY_KEY: 'sahayak_last_query',
  LANGUAGE_KEY: 'sahayak_language',
  REQUEST_TIMEOUT_MS: 25_000,
  USE_CONTINUOUS_VOICE: true,
} as const;
