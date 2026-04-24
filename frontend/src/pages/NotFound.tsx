import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="text-center">
        <p className="eyebrow mb-3">404</p>
        <h1 className="mb-2 text-4xl">Page not found</h1>
        <p className="mb-6 text-[var(--color-ink-muted)]">That page doesn't exist.</p>
        <Link to="/" className="btn-cta">
          Back home
        </Link>
      </div>
    </div>
  );
}
