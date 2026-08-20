"use client";

import { MessageSquare, Send, Bot, Sparkles, BookOpen } from "lucide-react";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
          <MessageSquare className="w-6 h-6 text-indigo-400" />
          AI Knowledge Chat
        </h1>
        <p className="text-slate-400 text-xs mt-1">
          Ask questions against indexed documents with source-grounded citations and streaming responses.
        </p>
      </div>

      {/* Chat Container Placeholder */}
      <div className="h-[520px] rounded-2xl bg-slate-900 border border-slate-800 flex flex-col justify-between overflow-hidden">
        {/* Messages List Area */}
        <div className="p-6 flex-1 flex flex-col items-center justify-center text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-indigo-950/60 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
            <Bot className="w-6 h-6" />
          </div>
          <div className="max-w-md space-y-2">
            <h3 className="text-sm font-semibold text-slate-200">Interactive RAG Chat (Phase 3)</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Once documents are indexed, you will be able to converse with the knowledge assistant here. 
              Responses will stream token-by-token via Server-Sent Events (SSE) with interactive citation chips.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Streaming LLM + pgvector similarity search ready in Phase 3</span>
          </div>
        </div>

        {/* Input Bar Placeholder */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40 flex items-center gap-3">
          <input
            type="text"
            disabled
            placeholder="Ask anything about your uploaded documents... (Active in Phase 3)"
            className="flex-1 px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-500 cursor-not-allowed focus:outline-none"
          />
          <button
            disabled
            className="p-2.5 rounded-lg bg-indigo-600/40 text-slate-400 cursor-not-allowed border border-indigo-500/20"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
