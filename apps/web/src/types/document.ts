export interface DocumentItem {
  id: string;
  name: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  source_url?: string | null;
  status: string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
