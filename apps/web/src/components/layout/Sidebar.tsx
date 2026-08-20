"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { 
  Bot, 
  Files, 
  MessageSquare, 
  LayoutDashboard, 
  Layers, 
  Database,
  Terminal,
  LogOut,
  UserCheck
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Documents", href: "/documents", icon: Files },
  { name: "AI Chat", href: "/chat", icon: MessageSquare },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-sm text-slate-100 leading-none">Knowledge AI</h1>
            <span className="text-[10px] text-indigo-400 font-mono">Phase 2: Auth Active</span>
          </div>
        </div>

        {/* Navigation links */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Main Navigation
          </div>
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                )}
              >
                <Icon className={cn("w-4 h-4", isActive ? "text-indigo-400" : "text-slate-400")} />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User Status & Architecture Footer */}
      <div className="p-4 border-t border-slate-800 space-y-3">
        {user && (
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <UserCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <div className="min-w-0">
                <p className="text-[11px] font-mono text-slate-300 truncate">{user.email}</p>
                <p className="text-[9px] text-slate-500">Authenticated Session</p>
              </div>
            </div>
            <button
              onClick={() => logout()}
              className="text-slate-400 hover:text-red-400 p-1 transition"
              title="Logout"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <div className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-1 text-[11px] text-slate-400">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5"><Layers className="w-3 h-3 text-indigo-400" /> Next.js 15</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5"><Terminal className="w-3 h-3 text-emerald-400" /> FastAPI + JWT</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5"><Database className="w-3 h-3 text-sky-400" /> Postgres + pgvector</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
