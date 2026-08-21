export interface Citation {
  source_id: number;
  document_id: string;
  document_name: string;
  source_url?: string | null;
  chunk_id: string;
  page?: number;
  heading?: string;
  content_preview: string;
  score: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface ConversationListResponse {
  items: Conversation[];
  total: number;
}
