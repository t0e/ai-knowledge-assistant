"use client";

import { useEffect, useState } from "react";
import { HealthResponse } from "@/types/health";
import { fetchHealth, API_BASE_URL } from "@/lib/api";
import { 
  Database, 
  Server, 
  Cpu, 
  ShieldCheck, 
  Activity, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  FileText,
  MessageSquare,
  ArrowRight,
  ExternalLink
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadHealth = async () => {
      try {
        setLoading(true);
        const data = await fetchHealth();
        setHealth(data);
        setError(null);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to connect to backend");
        setHealth(null);
      } finally {
        setLoading(false);
      }
    };
    loadHealth();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-indigo-900/40 via-slate-900 to-slate-900 border border-indigo-500/20 p-8">
        <div className="max-w-3xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-xs font-semibold text-indigo-300">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            Phase 1 Foundation Active
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            AI Knowledge Assistant
          </h1>
          <p className="text-slate-300 text-sm leading-relaxed">
            A production-quality RAG (Retrieval-Augmented Generation) platform powered by Next.js 15, FastAPI, 
            PostgreSQL with pgvector, and Redis.
          </p>
          <div className="pt-2 flex flex-wrap items-center gap-4">
            <a
              href={`${API_BASE_URL}/docs`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition shadow-md shadow-indigo-600/20"
            >
              <span>Swagger API Docs</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <Link
              href="/documents"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition"
            >
              <span>Manage Documents</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Live System Diagnostics & Infrastructure Status */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-400" />
            Infrastructure & Diagnostics
          </h2>
          <span className="text-xs text-slate-400 font-mono">Endpoint: {API_BASE_URL}/api/v1/health</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* FastAPI Card */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-emerald-950/60 border border-emerald-800/60 flex items-center justify-center text-emerald-400">
                <Server className="w-5 h-5" />
              </div>
              {loading ? (
                <span className="text-xs text-slate-400">Checking...</span>
              ) : health ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3" /> Online
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-950 text-red-300 border border-red-800">
                  <XCircle className="w-3 h-3" /> Offline
                </span>
              )}
            </div>
            <div>
              <h3 className="font-semibold text-sm text-slate-200">FastAPI Backend</h3>
              <p className="text-xs text-slate-400 mt-1">Python 3.12, Async SQLAlchemy 2.0, Pydantic v2</p>
            </div>
            <div className="pt-2 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
              <span>Environment</span>
              <span className="font-mono text-slate-300">{health?.environment || "development"}</span>
            </div>
          </div>

          {/* PostgreSQL + pgvector Card */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-sky-950/60 border border-sky-800/60 flex items-center justify-center text-sky-400">
                <Database className="w-5 h-5" />
              </div>
              {loading ? (
                <span className="text-xs text-slate-400">Checking...</span>
              ) : health?.database.connected && health?.database.pgvector_installed ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3" /> pgvector Ready
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950 text-amber-300 border border-amber-800">
                  <AlertCircle className="w-3 h-3" /> Check Required
                </span>
              )}
            </div>
            <div>
              <h3 className="font-semibold text-sm text-slate-200">PostgreSQL 16</h3>
              <p className="text-xs text-slate-400 mt-1">pgvector extension enabled for HNSW vector search</p>
            </div>
            <div className="pt-2 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
              <span>pgvector Installed</span>
              <span className="font-mono text-slate-300">
                {health?.database.pgvector_installed ? "true (enabled)" : "false"}
              </span>
            </div>
          </div>

          {/* Redis Card */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-red-950/60 border border-red-800/60 flex items-center justify-center text-red-400">
                <Cpu className="w-5 h-5" />
              </div>
              {loading ? (
                <span className="text-xs text-slate-400">Checking...</span>
              ) : health?.redis.connected ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-950 text-red-300 border border-red-800">
                  <XCircle className="w-3 h-3" /> Disconnected
                </span>
              )}
            </div>
            <div>
              <h3 className="font-semibold text-sm text-slate-200">Redis 7 Alpine</h3>
              <p className="text-xs text-slate-400 mt-1">Broker & queue backend for Celery task processing</p>
            </div>
            <div className="pt-2 border-t border-slate-800/80 text-xs text-slate-400 flex justify-between">
              <span>Status</span>
              <span className="font-mono text-slate-300">{health?.redis.status || "unreachable"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Navigation Placeholders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
        <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-950/60 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-semibold text-slate-100">Knowledge Documents</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Upload PDF and Markdown files, track background chunking and embedding progress, and inspect stored document metadata.
            </p>
          </div>
          <div className="pt-6">
            <Link
              href="/documents"
              className="inline-flex items-center gap-2 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
            >
              View Document Manager <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-950/60 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
              <MessageSquare className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-semibold text-slate-100">AI Assistant Chat</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Ask questions about your uploaded documents, retrieve relevant vector chunks, and receive streamed responses with verifiable citations.
            </p>
          </div>
          <div className="pt-6">
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
            >
              Open AI Chat <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
