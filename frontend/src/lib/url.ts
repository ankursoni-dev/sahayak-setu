/**
 * Defensive URL helpers for rendering backend-supplied links.
 *
 * Backends can be compromised, ingest pipelines can pick up malicious sources, and
 * curated data drifts. We accept only http(s) URLs at the rendering layer so a
 * `javascript:`/`data:`/`vbscript:` payload from any data source never reaches an
 * `<a href>` attribute. Returns the original string (untouched) when safe, or
 * `undefined` when the caller should render plain text instead of a link.
 */

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:']);

export function safeHref(input: string | null | undefined): string | undefined {
  if (!input) return undefined;
  const trimmed = input.trim();
  if (!trimmed) return undefined;
  // Reject obvious dangerous schemes by string match first — `new URL(...)` will
  // happily parse `javascript:alert(1)` as a valid URL with protocol `javascript:`.
  try {
    const parsed = new URL(trimmed);
    if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) return undefined;
    return trimmed;
  } catch {
    return undefined;
  }
}
