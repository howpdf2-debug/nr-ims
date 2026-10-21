import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { useLocation } from "react-router-dom";

interface BoundaryProps {
  children: ReactNode;
  resetKey: string;
}
interface BoundaryState {
  error: Error | null;
  resetKey: string;
}

/** Catches render errors so one broken page never blanks the whole NOC console. */
class Boundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<BoundaryState> {
    return { error };
  }

  // Navigating to another route clears the error so the rest of the app stays usable.
  static getDerivedStateFromProps(props: BoundaryProps, state: BoundaryState): Partial<BoundaryState> | null {
    return props.resetKey !== state.resetKey ? { error: null, resetKey: props.resetKey } : null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI render error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="data-card" style={{ margin: "2rem", maxWidth: 640 }}>
        <h2 style={{ marginTop: 0, color: "var(--accent-red)" }}>Something went wrong on this page</h2>
        <p style={{ color: "var(--text-muted)" }}>
          The rest of the application is unaffected. You can go back or return to the dashboard.
        </p>
        <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", opacity: 0.8 }}>{this.state.error.message}</pre>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
          <button className="btn" style={{ width: "auto" }} onClick={() => window.history.back()}>Go back</button>
          <button className="btn" style={{ width: "auto" }} onClick={() => window.location.assign("/dashboard")}>
            Dashboard
          </button>
        </div>
      </div>
    );
  }
}

export default function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return <Boundary resetKey={pathname}>{children}</Boundary>;
}
