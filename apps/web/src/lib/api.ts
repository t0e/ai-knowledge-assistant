import { HealthResponse } from '@/types/health';
import { User, ApiErrorDetail } from '@/types/auth';
import { DocumentItem, DocumentListResponse } from '@/types/document';

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

  // Documents (Phase 3)
  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);

    return request<DocumentItem>('/api/v1/documents', {
      method: 'POST',
      body: formData,
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
};

export const fetchHealth = api.getHealth;
