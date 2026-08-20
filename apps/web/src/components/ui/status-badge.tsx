"use client";

import { useEffect, useState } from "react";
import { HealthResponse } from "@/types/health";
import { fetchHealth } from "@/lib/api";
import { Activity, CheckCircle2, AlertTriangle, XCircle, RefreshCw } from "lucide-react";

export function StatusBadge() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchHealth();
      setHealth(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Backend unreachable");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, []);

  if (loading && !health && !error) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-xs text-slate-400">
        <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" />
        <span>Connecting API...</span>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-950/60 border border-red-800 text-xs text-red-300">
        <XCircle className="w-3.5 h-3.5 text-red-400" />
        <span>API Offline</span>
        <button
          onClick={checkHealth}
          className="ml-1 hover:text-white transition-colors"
          title="Retry"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>
    );
  }

  const isHealthy = health.status === "healthy";

  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium ${
          isHealthy
            ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
            : "bg-amber-950/60 border-amber-800 text-amber-300"
        }`}
      >
        {isHealthy ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        ) : (
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
        )}
        <span>{isHealthy ? "System Operational" : "Degraded"}</span>
      </div>
    </div>
  );
}
