"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, ApiError } from "@/lib/api";
import { DocumentItem } from "@/types/document";
import {
  Upload,
  FileText,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  FileCode,
  Files,
  RefreshCw,
  Globe,
  ExternalLink,
  RotateCw,
  Plus,
} from "lucide-react";

export default function DocumentsPage() {
  const [activeTab, setActiveTab] = useState<"file" | "url">("file");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [submittingUrl, setSubmittingUrl] = useState(false);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgressFile, setUploadProgressFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async (targetPage = 1, silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.listDocuments(targetPage, 10);
      setDocuments(data.items);
      setTotal(data.total);
      setPage(data.page);
      setTotalPages(data.total_pages);
    } catch (err: unknown) {
      if (!silent) {
        if (err instanceof ApiError) {
          setError(err.data.detail || "Failed to load documents.");
        } else if (err instanceof Error) {
          setError(err.message);
        }
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments(1);
  }, [fetchDocuments]);

  // Phase 7/8: Live background polling when any document is in 'uploaded' or 'processing' state
  useEffect(() => {
    const hasPendingDocs = documents.some(
      (d) => d.status === "uploaded" || d.status === "processing"
    );

    if (!hasPendingDocs) return;

    const intervalId = setInterval(() => {
      fetchDocuments(page, true);
    }, 2000);

    return () => clearInterval(intervalId);
  }, [documents, page, fetchDocuments]);

  const handleFileUpload = async (file: File) => {
    setError(null);
    setSuccess(null);

    // Client-side validations
    const allowedExtensions = [".pdf", ".md", ".markdown"];
    const fileExt = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowedExtensions.includes(fileExt)) {
      setError(`Unsupported file type '${fileExt}'. Please upload a PDF or Markdown (.md) file.`);
      return;
    }

    const maxBytes = 20 * 1024 * 1024;
    if (file.size > maxBytes) {
      setError(`File size (${formatFileSize(file.size)}) exceeds the 20 MB limit.`);
      return;
    }

    if (file.size === 0) {
      setError("The selected file is empty.");
      return;
    }

    setUploading(true);
    setUploadProgressFile(file.name);

    try {
      const newDoc = await api.uploadDocument(file);
      setSuccess(`Successfully uploaded "${newDoc.name}"`);
      await fetchDocuments(1);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to upload document.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during upload.");
      }
    } finally {
      setUploading(false);
      setUploadProgressFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!websiteUrl.trim()) return;

    setError(null);
    setSuccess(null);
    setSubmittingUrl(true);

    try {
      const newDoc = await api.ingestUrl(websiteUrl.trim());
      setSuccess(`Successfully added website source "${newDoc.name}"`);
      setWebsiteUrl("");
      await fetchDocuments(1);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to add website URL.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred while adding website.");
      }
    } finally {
      setSubmittingUrl(false);
    }
  };

  const handleReprocess = async (doc: DocumentItem) => {
    setReprocessingId(doc.id);
    setError(null);
    try {
      await api.reprocessDocument(doc.id);
      setSuccess(`Reprocessing triggered for "${doc.name}"`);
      await fetchDocuments(page);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to reprocess document.");
      } else if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setReprocessingId(null);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await handleFileUpload(file);
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${doc.name}"? This action cannot be undone.`
    );
    if (!confirmed) return;

    setDeletingId(doc.id);
    setError(null);
    try {
      await api.deleteDocument(doc.id);
      setSuccess(`Document "${doc.name}" deleted.`);
      await fetchDocuments(page);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.data.detail || "Failed to delete document.");
      } else if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setDeletingId(null);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "Webpage";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string): string => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Knowledge Sources</h1>
          <p className="text-xs text-slate-400 mt-1">
            Ingest and manage files (PDF, Markdown) and public web URLs for RAG knowledge retrieval.
          </p>
        </div>
        <button
          onClick={() => fetchDocuments(page)}
          disabled={loading}
          className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 rounded-lg transition"
          title="Refresh List"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-xl bg-red-950/50 border border-red-800/60 text-red-300 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-200 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {success && (
        <div className="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800/60 text-emerald-300 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{success}</span>
          </div>
          <button
            onClick={() => setSuccess(null)}
            className="text-emerald-400 hover:text-emerald-200 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Ingestion Mode Switcher & Forms */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <button
            type="button"
            onClick={() => setActiveTab("file")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
              activeTab === "file"
                ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            Upload File
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("url")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
              activeTab === "url"
                ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            Add Website
          </button>
        </div>

        {activeTab === "file" ? (
          /* Drag & Drop Upload Zone */
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 ${
              isDragging
                ? "border-indigo-500 bg-indigo-950/20 scale-[1.005]"
                : "border-slate-800 hover:border-slate-700 bg-slate-900/40 hover:bg-slate-900/70"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
              accept=".pdf,.md,.markdown,application/pdf,text/markdown,text/plain"
              className="hidden"
            />

            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                {uploading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                ) : (
                  <Upload className="w-6 h-6" />
                )}
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-200">
                  {uploading
                    ? `Uploading ${uploadProgressFile}...`
                    : "Drop files here or click to browse"}
                </p>
                <p className="text-xs text-slate-500 mt-1 font-mono">
                  Supported: PDF (.pdf), Markdown (.md, .markdown) • Maximum size: 20 MB
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* Add Website URL Form */
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Webpage URL
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Globe className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="url"
                      value={websiteUrl}
                      onChange={(e) => setWebsiteUrl(e.target.value)}
                      placeholder="https://example.com/documentation"
                      required
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={submittingUrl || !websiteUrl.trim()}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition shadow-lg shadow-indigo-600/20 shrink-0"
                  >
                    {submittingUrl ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Plus className="w-3.5 h-3.5" />
                    )}
                    Add Website
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 font-mono">
                Only public HTTP and HTTPS webpages are accepted. Internal IPs and local hostnames are blocked (SSRF protection).
              </p>
            </form>
          </div>
        )}
      </div>

      {/* Documents Table / List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Files className="w-4 h-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-slate-200">
              Uploaded Documents ({total})
            </h2>
          </div>
        </div>

        {loading && documents.length === 0 ? (
          <div className="p-12 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
            <span className="text-xs font-mono">Loading documents...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center bg-slate-900/30 rounded-2xl border border-slate-800/80 space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-800/50 flex items-center justify-center text-slate-500 mx-auto">
              <FileText className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-slate-300">No documents found</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Upload your first PDF or Markdown document above to begin building your knowledge assistant.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl shadow-xl">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/70 border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Document Name</th>
                  <th className="px-4 py-3.5">Type</th>
                  <th className="px-4 py-3.5">Size</th>
                  <th className="px-4 py-3.5">Uploaded</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {documents.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-slate-800/30 transition-colors duration-150"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                          {doc.file_type === "website" ? (
                            <Globe className="w-4 h-4 text-emerald-400" />
                          ) : doc.file_type === "pdf" ? (
                            <FileText className="w-4 h-4 text-rose-400" />
                          ) : (
                            <FileCode className="w-4 h-4 text-sky-400" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-slate-200 truncate max-w-xs sm:max-w-md">
                            {doc.name}
                          </p>
                          {doc.source_url ? (
                            <a
                              href={doc.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] text-indigo-400 hover:text-indigo-300 font-mono truncate flex items-center gap-1 mt-0.5 hover:underline"
                            >
                              <span>{doc.source_url}</span>
                              <ExternalLink className="w-3 h-3 shrink-0" />
                            </a>
                          ) : (
                            <p className="text-[10px] text-slate-500 font-mono truncate">
                              ID: {doc.id}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border ${
                          doc.file_type === "website"
                            ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/80"
                            : doc.file_type === "pdf"
                            ? "bg-rose-950/60 text-rose-300 border-rose-800/80"
                            : "bg-sky-950/60 text-sky-300 border-sky-800/80"
                        }`}
                      >
                        {doc.file_type}
                      </span>
                    </td>
                    <td className="px-4 py-4 font-mono text-slate-400">
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td className="px-4 py-4 text-slate-400">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-1">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium w-fit ${
                            doc.status === "uploaded"
                              ? "bg-sky-950/80 text-sky-400 border border-sky-800"
                              : doc.status === "ready"
                              ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800"
                              : doc.status === "processing"
                              ? "bg-amber-950/80 text-amber-300 border border-amber-800/80 shadow-sm"
                              : "bg-red-950/80 text-red-400 border border-red-800"
                          }`}
                        >
                          {doc.status === "processing" && (
                            <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                          )}
                          {doc.status === "ready" && (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          )}
                          {doc.status === "failed" && (
                            <AlertCircle className="w-3 h-3 text-red-400" />
                          )}
                          {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                        </span>
                        {doc.status === "failed" && doc.error_message && (
                          <span
                            className="text-[10px] text-red-400/80 max-w-xs truncate font-mono"
                            title={doc.error_message}
                          >
                            {doc.error_message}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleReprocess(doc)}
                          disabled={
                            reprocessingId === doc.id ||
                            doc.status === "processing" ||
                            doc.status === "uploaded"
                          }
                          className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-300 hover:bg-indigo-950/40 transition disabled:opacity-40"
                          title="Reprocess Knowledge Source"
                        >
                          {reprocessingId === doc.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                          ) : (
                            <RotateCw className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={() => handleDelete(doc)}
                          disabled={deletingId === doc.id}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/40 transition disabled:opacity-50"
                          title="Delete Knowledge Source"
                        >
                          {deletingId === doc.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-red-400" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="px-6 py-3 bg-slate-950/50 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>
                  Page {page} of {totalPages}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => fetchDocuments(page - 1)}
                    disabled={page <= 1 || loading}
                    className="px-3 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 rounded transition"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => fetchDocuments(page + 1)}
                    disabled={page >= totalPages || loading}
                    className="px-3 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 rounded transition"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
