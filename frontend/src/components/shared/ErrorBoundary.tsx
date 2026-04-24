import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary caught', error, info);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="card-soft max-w-md p-8 text-center">
          <p className="eyebrow mb-3">Something broke</p>
          <h2 className="text-2xl mb-2">We hit a snag</h2>
          <p className="text-[var(--color-ink-muted)] text-sm mb-6">{this.state.message || 'An unexpected error occurred.'}</p>
          <button type="button" className="btn-cta" onClick={this.handleReload}>
            Reload
          </button>
        </div>
      </div>
    );
  }
}
