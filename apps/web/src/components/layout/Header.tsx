"use client";

import { useAuth } from "@/context/AuthContext";
import { StatusBadge } from "@/components/ui/status-badge";
import { Server, User, LogOut } from "lucide-react";

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Server className="w-4 h-4 text-indigo-400" />
          <span className="text-slate-200 font-semibold">AI Knowledge Assistant Platform</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <StatusBadge />

        {user && (
          <div className="flex items-center gap-3 pl-4 border-l border-slate-800">
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <div className="w-7 h-7 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                <User className="w-3.5 h-3.5" />
              </div>
              <span className="font-mono text-slate-300 hidden sm:inline">{user.email}</span>
            </div>

            <button
              onClick={() => logout()}
              className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/40 transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
