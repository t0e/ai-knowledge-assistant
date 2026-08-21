"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import { Conversation, Message, Citation } from "@/types/chat";
import { DocumentItem } from "@/types/document";
import {
  Send,
  Bot,
  User as UserIcon,
  BookOpen,
  Plus,
  Trash2,
  Filter,
  CheckSquare,
  Square,
  Sparkles,
  Loader2,
  StopCircle,
  MessageSquare,
  AlertCircle,
  Globe,
  ExternalLink,
  ChevronUp,
  ChevronDown,
} from "lucide-react";

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  
  const [inputQuery, setInputQuery] = useState("");
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingTokenContent, setStreamingTokenContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  
  const [error, setError] = useState<string | null>(null);
  const [showDocFilter, setShowDocFilter] = useState(false);
  const [deletingConvId, setDeletingConvId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingTokenContent]);

  // 1. Initial Load: Fetch Conversations & User's Ready Documents
  const loadInitialData = useCallback(async () => {
    setLoadingConversations(true);
    setError(null);
    try {
      const [convData, docData] = await Promise.all([
        api.listConversations(1, 50),
        api.listDocuments(1, 100),
      ]);
      setConversations(convData.items);
      const readyDocs = docData.items.filter((d: DocumentItem) => d.status === "ready");
      setDocuments(readyDocs);

      if (convData.items.length > 0) {
        setActiveConvId(convData.items[0].id);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to load chat history.");
      } else if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // 2. Fetch Messages when active conversation changes
  const loadMessages = useCallback(async (convId: string) => {
    setLoadingMessages(true);
    setError(null);
    try {
      const detail = await api.getConversation(convId);
      setMessages(detail.messages);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to load conversation messages.");
      } else if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    if (activeConvId) {
      loadMessages(activeConvId);
    } else {
      setMessages([]);
    }
  }, [activeConvId, loadMessages]);

  // 3. Create New Conversation
  const handleCreateNewConversation = async () => {
    setError(null);
    try {
      const newConv = await api.createConversation("New Chat");
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setMessages([]);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to create conversation.");
      }
    }
  };

  // 4. Delete Conversation
  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmed = window.confirm("Delete this conversation?");
    if (!confirmed) return;

    setDeletingConvId(convId);
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        const remaining = conversations.filter((c) => c.id !== convId);
        setActiveConvId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to delete conversation.");
      }
    } finally {
      setDeletingConvId(null);
    }
  };

  // 5. Send Message & Stream RAG Response
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim() || isStreaming) return;

    const queryText = inputQuery.trim();
    setInputQuery("");

    // If no active conversation exists, create one first
    let currentConvId: string = activeConvId || "";
    if (!currentConvId) {
      try {
        const newConv = await api.createConversation(queryText.slice(0, 30));
        setConversations((prev) => [newConv, ...prev]);
        setActiveConvId(newConv.id);
        currentConvId = newConv.id;
      } catch (err: unknown) {
        setError("Failed to initialize conversation.");
        return;
      }
    }

    // Optimistically add user message to UI
    const optimisticUserMsg: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: currentConvId,
      role: "user",
      content: queryText,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);

    setIsStreaming(true);
    setStreamingTokenContent("");
    setStreamingCitations([]);
    setActiveCitation(null);
    setError(null);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    let accumulatedTokens = "";
    let accumulatedCitations: Citation[] = [];

    await api.streamMessage(
      currentConvId,
      queryText,
      selectedDocIds.length > 0 ? selectedDocIds : null,
      (token: string) => {
        accumulatedTokens += token;
        setStreamingTokenContent((prev) => prev + token);
      },
      (citations: Citation[]) => {
        accumulatedCitations = citations;
        setStreamingCitations(citations);
      },
      (data) => {
        // Complete event: finalize assistant message
        const finalAssistantMsg: Message = {
          id: data.message_id || `asst-${Date.now()}`,
          conversation_id: currentConvId as string,
          role: "assistant",
          content: accumulatedTokens,
          citations: accumulatedCitations,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, finalAssistantMsg]);
        setIsStreaming(false);
        setStreamingTokenContent("");
        setStreamingCitations([]);
        abortControllerRef.current = null;

        // Update conversation title if changed
        setConversations((prev) =>
          prev.map((c) =>
            c.id === currentConvId
              ? {
                  ...c,
                  title: c.title === "New Conversation" || c.title === "New Chat" ? queryText.slice(0, 35) : c.title,
                  message_count: c.message_count + 2,
                  updated_at: new Date().toISOString(),
                }
              : c
          )
        );
      },
      (streamError: string) => {
        setError(streamError);
        setIsStreaming(false);
        setStreamingTokenContent("");
        abortControllerRef.current = null;
      },
      abortController.signal
    );
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      if (streamingTokenContent) {
        const partialMsg: Message = {
          id: `partial-${Date.now()}`,
          conversation_id: activeConvId || "",
          role: "assistant",
          content: streamingTokenContent + " [Interrupted]",
          citations: streamingCitations,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, partialMsg]);
      }
      setStreamingTokenContent("");
      setStreamingCitations([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const toggleDocSelection = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  // Helper to render message with interactive clickable citation badges
  const renderMessageContent = (content: string, citations: Citation[]) => {
    const parts = content.split(/(\[\d+\])/g);
    return (
      <span className="whitespace-pre-wrap leading-relaxed">
        {parts.map((part, i) => {
          const match = part.match(/\[(\d+)\]/);
          if (match) {
            const srcNum = parseInt(match[1], 10);
            const foundCitation = citations.find((c) => c.source_id === srcNum);
            return (
              <button
                key={i}
                type="button"
                onClick={() => foundCitation && setActiveCitation(foundCitation)}
                className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-[11px] font-mono font-semibold rounded bg-indigo-950/80 text-indigo-300 border border-indigo-700/60 hover:bg-indigo-900 hover:text-indigo-100 transition-colors shadow-sm cursor-pointer"
                title={
                  foundCitation
                    ? `Source ${srcNum}: ${foundCitation.document_name} (${foundCitation.page ? `Page ${foundCitation.page}` : foundCitation.heading || "Excerpt"})`
                    : `Source [${srcNum}]`
                }
              >
                [{srcNum}]
              </button>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </span>
    );
  };

  return (
    <div className="flex h-[calc(100vh-6.5rem)] gap-4">
      {/* ========================================================================= */}
      {/* Left Sidebar: Conversations & Source Filter */}
      {/* ========================================================================= */}
      <aside className="w-80 flex flex-col bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 overflow-hidden shrink-0">
        {/* New Chat Button */}
        <button
          onClick={handleCreateNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition duration-150"
        >
          <Plus className="w-4 h-4" />
          <span>New Conversation</span>
        </button>

        {/* Source Scope Filter Toggle */}
        <div className="mt-3 border-b border-slate-800 pb-3">
          <button
            onClick={() => setShowDocFilter(!showDocFilter)}
            className="w-full flex items-center justify-between px-2.5 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg transition"
          >
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-indigo-400" />
              <span>Scope Sources</span>
              <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-300 font-mono">
                {selectedDocIds.length === 0 ? "All Docs" : `${selectedDocIds.length} active`}
              </span>
            </div>
            {showDocFilter ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {showDocFilter && (
            <div className="mt-2 p-2 bg-slate-950/60 rounded-xl border border-slate-800 max-h-36 overflow-y-auto space-y-1.5">
              {documents.length === 0 ? (
                <p className="text-[11px] text-slate-500 italic p-1">No ready documents uploaded yet.</p>
              ) : (
                documents.map((doc) => {
                  const isSelected = selectedDocIds.includes(doc.id);
                  return (
                    <div
                      key={doc.id}
                      onClick={() => toggleDocSelection(doc.id)}
                      className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-800/50 cursor-pointer text-xs transition"
                    >
                      {isSelected ? (
                        <CheckSquare className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      ) : (
                        <Square className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                      )}
                      <span className="truncate text-slate-300 font-mono text-[11px]">{doc.name}</span>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto mt-3 space-y-1 pr-1">
          <div className="flex items-center justify-between px-2 mb-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            <span>Recent Chats</span>
            <span>{conversations.length}</span>
          </div>

          {loadingConversations ? (
            <div className="p-8 text-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-400" />
              <span className="text-xs">Loading chats...</span>
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-xs">
              No conversations yet. Start a new chat above!
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConvId;
              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveConvId(conv.id)}
                  className={`group relative flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition text-xs ${
                    isActive
                      ? "bg-slate-800/90 text-slate-100 font-medium border border-slate-700/60 shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate pr-6">
                    <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-indigo-400" : "text-slate-500"}`} />
                    <span className="truncate">{conv.title}</span>
                  </div>

                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    disabled={deletingConvId === conv.id}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 hover:bg-red-950/40 rounded transition"
                    title="Delete Conversation"
                  >
                    {deletingConvId === conv.id ? (
                      <Loader2 className="w-3 h-3 animate-spin text-red-400" />
                    ) : (
                      <Trash2 className="w-3 h-3" />
                    )}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ========================================================================= */}
      {/* Center: Main Chat Viewport */}
      {/* ========================================================================= */}
      <main className="flex-1 flex flex-col bg-slate-900/60 border border-slate-800/80 rounded-2xl overflow-hidden">
        {/* Error Banner */}
        {error && (
          <div className="p-3 bg-red-950/50 border-b border-red-800/60 text-red-300 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200 text-xs">✕</button>
          </div>
        )}

        {/* Message Feed Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loadingMessages ? (
            <div className="h-full flex items-center justify-center text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mr-2" />
              <span className="text-xs font-mono">Loading messages...</span>
            </div>
          ) : messages.length === 0 && !isStreaming ? (
            /* Empty State / Starter Suggestions */
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-inner">
                <Bot className="w-7 h-7" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-200">Grounded Knowledge Assistant</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-md">
                  Ask questions about your uploaded documents. Answers are strictly grounded in retrieved passages with verified source citations.
                </p>
              </div>

              {documents.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4 max-w-lg w-full text-left">
                  <button
                    onClick={() => {
                      setInputQuery("Summarize the key architectural principles in my documents.");
                    }}
                    className="p-3 rounded-xl bg-slate-950/40 border border-slate-800 hover:border-indigo-500/40 text-xs text-slate-300 hover:text-white transition"
                  >
                    💡 <span className="font-semibold">Summarize architecture</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">Overview of uploaded system designs</p>
                  </button>
                  <button
                    onClick={() => {
                      setInputQuery("What security and authentication policies are specified?");
                    }}
                    className="p-3 rounded-xl bg-slate-950/40 border border-slate-800 hover:border-indigo-500/40 text-xs text-slate-300 hover:text-white transition"
                  >
                    🔒 <span className="font-semibold">Security policies</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">Review auth and cookie configurations</p>
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Chronological Message Bubbles */
            <>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3.5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" && (
                    <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 text-indigo-400 mt-1">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-2xl rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                      msg.role === "user"
                        ? "bg-indigo-600 text-white rounded-br-none shadow-md shadow-indigo-600/10 font-medium"
                        : "bg-slate-950/70 border border-slate-800/80 text-slate-200 rounded-bl-none shadow-sm"
                    }`}
                  >
                    {msg.role === "user" ? (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    ) : (
                      <>
                        {renderMessageContent(msg.content, msg.citations || [])}

                        {/* Citations Pill Bar */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-wrap items-center gap-1.5">
                            <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider flex items-center gap-1">
                              <BookOpen className="w-3 h-3 text-indigo-400" /> Sources:
                            </span>
                            {msg.citations.map((c) => (
                              <button
                                key={c.source_id}
                                onClick={() => setActiveCitation(c)}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/40 text-[10px] font-mono text-slate-300 hover:text-indigo-200 transition"
                              >
                                <span>[{c.source_id}]</span>
                                <span className="max-w-[120px] truncate">{c.document_name}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {msg.role === "user" && (
                    <div className="w-8 h-8 rounded-xl bg-slate-800 flex items-center justify-center shrink-0 text-slate-300 mt-1">
                      <UserIcon className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))}

              {/* Streaming Assistant Response In Progress */}
              {isStreaming && (
                <div className="flex gap-3.5 justify-start animate-fade-in">
                  <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 text-indigo-400 mt-1">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                  <div className="max-w-2xl rounded-2xl px-4 py-3 text-xs leading-relaxed bg-slate-950/70 border border-slate-800/80 text-slate-200 rounded-bl-none">
                    {streamingTokenContent ? (
                      renderMessageContent(streamingTokenContent, streamingCitations)
                    ) : (
                      <span className="inline-flex items-center gap-2 text-slate-400 font-mono">
                        <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
                        Searching documents & generating grounded response...
                      </span>
                    )}
                    <span className="inline-block w-1.5 h-3.5 bg-indigo-400 ml-1 animate-pulse" />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Selected Citation Detail Popover / Drawer */}
        {activeCitation && (
          <div className="mx-6 mb-2 p-3 bg-slate-950 border border-indigo-500/30 rounded-xl text-xs text-slate-300 shadow-xl flex items-start justify-between gap-3 animate-fade-in">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 rounded bg-indigo-600 text-white font-mono text-[10px] font-bold">
                  Source [{activeCitation.source_id}]
                </span>
                <span className="font-semibold text-slate-200">{activeCitation.document_name}</span>
                <span className="text-slate-500 font-mono text-[10px]">
                  {activeCitation.page
                    ? `Page ${activeCitation.page}`
                    : activeCitation.heading || "Document Root"}{" "}
                  • Score: {activeCitation.score}
                </span>
              </div>
              {activeCitation.source_url && (
                <div className="flex items-center gap-1">
                  <Globe className="w-3 h-3 text-emerald-400 shrink-0" />
                  <a
                    href={activeCitation.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 font-mono flex items-center gap-1 hover:underline truncate max-w-md"
                  >
                    <span>{activeCitation.source_url}</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                </div>
              )}
              <p className="text-[11px] text-slate-400 italic bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
                &ldquo;{activeCitation.content_preview}&rdquo;
              </p>
            </div>
            <button
              onClick={() => setActiveCitation(null)}
              className="text-slate-500 hover:text-slate-200 p-1 text-xs"
            >
              ✕
            </button>
          </div>
        )}

        {/* Bottom Input Area */}
        <div className="p-4 bg-slate-950/80 border-t border-slate-800">
          <form onSubmit={handleSendMessage} className="relative flex items-center gap-2">
            <textarea
              ref={textareaRef}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              rows={1}
              placeholder={
                documents.length === 0
                  ? "Upload documents first to start asking questions..."
                  : selectedDocIds.length > 0
                  ? `Ask about ${selectedDocIds.length} selected document(s)...`
                  : "Ask a question about your knowledge documents (Enter to send)..."
              }
              className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 resize-none max-h-32 transition disabled:opacity-50"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={handleStopGeneration}
                className="px-4 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shrink-0 shadow-lg shadow-red-600/20"
              >
                <StopCircle className="w-4 h-4" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!inputQuery.trim() || isStreaming}
                className="px-4 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold flex items-center gap-1.5 transition shrink-0 shadow-lg shadow-indigo-600/20 disabled:shadow-none"
              >
                <Send className="w-4 h-4" />
                <span>Send</span>
              </button>
            )}
          </form>
          <div className="flex items-center justify-between mt-2 px-1 text-[10px] text-slate-500 font-mono">
            <span>Shift + Enter for new line • Enter to submit</span>
            <span>{documents.length} document(s) indexed with pgvector</span>
          </div>
        </div>
      </main>
    </div>
  );
}
