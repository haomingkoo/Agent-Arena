import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface Props {
  children: ReactNode;
  routeName: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class RouteErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    error: null,
  };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`Route "${this.props.routeName}" crashed`, error, errorInfo);
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <div className="rounded-2xl border border-red/30 bg-bg-card p-6 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
          <p className="text-xs font-mono uppercase tracking-[0.24em] text-red/80">
            {this.props.routeName}
          </p>
          <h1 className="mt-3 text-2xl font-semibold text-text-primary">
            This route hit an unexpected error
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary">
            {this.state.error?.message ?? 'Something went wrong while rendering this page.'}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="cursor-pointer rounded-lg bg-cyan-accent px-4 py-2 font-medium text-bg-primary transition-opacity hover:opacity-90"
            >
              Reload page
            </button>
            <Link
              to="/"
              className="rounded-lg border border-border px-4 py-2 text-text-secondary no-underline transition-colors hover:border-cyan-accent/50 hover:text-text-primary"
            >
              Back to leaderboard
            </Link>
          </div>
        </div>
      </div>
    );
  }
}
