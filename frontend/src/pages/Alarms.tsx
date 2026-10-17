import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { AlertTriangle } from "lucide-react";

export default function Alarms() {
  // Note: We will build the full Alarms API later. For now, we display a placeholder.
  return (
    <div>
      <h1 style={{ marginBottom: '2rem' }}>Alarm Center</h1>
      <div className="data-card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
        <AlertTriangle size={48} color="var(--accent-amber)" style={{ margin: '0 auto 1rem' }} />
        <h2 style={{ color: 'white', marginBottom: '0.5rem' }}>Alarm Management Coming Soon</h2>
        <p style={{ color: 'var(--text-muted)' }}>This module will allow NOC operators to Acknowledge and Resolve incidents.</p>
      </div>
    </div>
  );
}
