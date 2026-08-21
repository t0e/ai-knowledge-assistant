import { HealthResponse } from '@/types/health';
import { User, ApiErrorDetail } from '@/types/auth';
import { DocumentItem, DocumentListResponse } from '@/types/document';
import { Conversation, ConversationListResponse, ConversationDetail, Citation } from '@/types/chat';

const getApiBaseUrl = (): string => {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

export const API_BASE_URL = getApiBaseUrl();

export class ApiError extends Error {
  status: number;
  data: ApiErrorDetail;

  constructor(status: number, data: ApiErrorDetail) {
    super(data.detail || data.title || `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const isFormData = options.body instanceof FormData;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (!isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  });

  if (!response.ok) {
    let errorData: ApiErrorDetail;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        title: 'Error',
        detail: response.statusText || 'An unexpected error occurred',
        status: response.status,
      };
    }
    throw new ApiError(response.status, errorData);
  }

  return response.json();
}

export const api = {
  // Health
  async getHealth(): Promise<HealthResponse> {
    const url = `${API_BASE_URL}/api/v1/health`;
    const res = await fetch(url, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    if (!res.ok && res.status !== 503) {
      throw new Error(`API health check failed with status ${res.status}`);
    }
    return res.json();
  },

  // Auth
  async register(email: string, password: string): Promise<User> {
    return request<User>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async login(email: string, password: string): Promise<User> {
    return request<User>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async logout(): Promise<{ message: string }> {
    return request<{ message: string }>('/api/v1/auth/logout', {
      method: 'POST',
    });
  },

  async getMe(): Promise<User> {
    return request<User>('/api/v1/auth/me', {
      method: 'GET',
    });
  },

  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);

    return request<DocumentItem>('/api/v1/documents', {
      method: 'POST',
      body: formData,
    });
  },

  async ingestUrl(url: string): Promise<DocumentItem> {
    return request<DocumentItem>('/api/v1/documents/url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  },

  async reprocessDocument(documentId: string): Promise<DocumentItem> {
    return request<DocumentItem>(`/api/v1/documents/${documentId}/reprocess`, {
      method: 'POST',
    });
  },

  async listDocuments(page = 1, pageSize = 20): Promise<DocumentListResponse> {
    return request<DocumentListResponse>(
      `/api/v1/documents?page=${page}&page_size=${pageSize}`,
      { method: 'GET' }
    );
  },

  async getDocument(documentId: string): Promise<DocumentItem> {
    return request<DocumentItem>(`/api/v1/documents/${documentId}`, {
      method: 'GET',
    });
  },

  async deleteDocument(documentId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/api/v1/documents/${documentId}`, {
      method: 'DELETE',
    });
  },
  // Conversations & RAG Chat (Phase 6)
  async createConversation(title?: string): Promise<Conversation> {
    return request<Conversation>('/api/v1/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    });
  },

  async listConversations(page = 1, pageSize = 50): Promise<ConversationListResponse> {
    return request<ConversationListResponse>(
      `/api/v1/conversations?page=${page}&page_size=${pageSize}`,
      { method: 'GET' }
    );
  },

  async getConversation(conversationId: string): Promise<ConversationDetail> {
    return request<ConversationDetail>(`/api/v1/conversations/${conversationId}`, {
      method: 'GET',
    });
  },

  async deleteConversation(conversationId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/api/v1/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  },

  async streamMessage(
    conversationId: string,
    content: string,
    documentIds: string[] | null,
    onToken: (token: string) => void,
    onCitations: (citations: Citation[]) => void,
    onDone: (data: { conversation_id: string; message_id: string }) => void,
    onError: (error: string) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const url = `${API_BASE_URL}/api/v1/conversations/${conversationId}/messages`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          content,
          document_ids: documentIds && documentIds.length > 0 ? documentIds : null,
          top_k: 5,
        }),
        signal,
      });

      if (!response.ok) {
        let errDetail = 'Failed to generate response';
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || errJson.title || errDetail;
        } catch {
          errDetail = response.statusText || errDetail;
        }
        onError(errDetail);
        return;
      }

      if (!response.body) {
        onError('No response stream received.');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = 'message';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.substring(6).trim();
          } else if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.substring(5).trim();
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent === 'token') {
                onToken(data.token || '');
              } else if (currentEvent === 'citations') {
                onCitations(data.citations || []);
              } else if (currentEvent === 'done') {
                onDone(data);
              } else if (currentEvent === 'error') {
                onError(data.error || 'Unknown stream error');
              }
            } catch {
              // Raw non-JSON fallback
              if (currentEvent === 'token') {
                onToken(dataStr);
              }
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        logger.info('Generation aborted by user');
        return;
      }
      onError(err instanceof Error ? err.message : 'Network error during streaming');
    }
  },
};

const logger = {
  info: (...args: unknown[]) => {
    if (process.env.NODE_ENV !== 'production') {
      console.log(...args);
    }
  },
};

export const fetchHealth = api.getHealth;
