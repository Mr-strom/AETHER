import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

// ---------- Types ----------

export interface QueryResponse {
  query_id: number;
  query: string;
  answer: string;
  citations: string[];
  confidence: string;
  confidence_score: number;
  response_time_ms: number;
  latency_ms: number;
  model_used: string;
  evidence: EvidencePiece[];
  conflicts?: string[];
  hops?: number;
  created_at: string;
}

export interface EvidencePiece {
  id: number;
  source_id: number;
  chunk_index: number;
  content: string;
  modality: string;
  page_number: number | null;
  confidence_score: number;
  metadata_json: {
    source_name: string;
    reason: string;
    evidence_id: string;
  };
}

export interface AirgapResult {
  all_green: boolean;
  signature_valid: boolean;
  network_isolated: boolean;
  attestation_hash: string;
  timestamp: string;
  errors: string[];
  warnings: string[];
}

export interface SourceItem {
  id: number;
  filename: string;
  file_type: string;
  file_path: string;
  file_hash: string;
  size_bytes: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface StatusUpdate {
  step: string;
  message: string;
}

export interface ConversationItem {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessageItem {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  citations_json: string[] | null;
  confidence: string | null;
  latency_ms: number | null;
  evidence_json: EvidencePiece[] | null;
  created_at: string;
}

// ---------- Retry logic ----------

async function withRetry<T>(
  fn: () => Promise<T>,
  onRetry?: (attempt: number, maxAttempts: number) => void,
  maxAttempts: number = 3,
): Promise<T> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === maxAttempts) throw err;
      onRetry?.(attempt, maxAttempts);
      await new Promise((r) => setTimeout(r, Math.pow(2, attempt) * 1000));
    }
  }
  throw new Error('Retry exhausted');
}

// ---------- Query ----------

export async function submitQuery(query: string): Promise<QueryResponse> {
  const res = await api.post<QueryResponse>('/query', { query });
  return res.data;
}

export function streamQuery(
  query: string,
  onStatus: (update: StatusUpdate) => void,
  onComplete: (response: QueryResponse) => void,
  onError: (error: string) => void,
): () => void {
  const url = `/api/query/stream?q=${encodeURIComponent(query)}`;
  const eventSource = new EventSource(url);

  eventSource.addEventListener('status', (event: MessageEvent) => {
    try {
      onStatus(JSON.parse(event.data) as StatusUpdate);
    } catch { /* ignore */ }
  });

  eventSource.addEventListener('complete', (event: MessageEvent) => {
    try {
      onComplete(JSON.parse(event.data) as QueryResponse);
    } catch { /* ignore */ }
    eventSource.close();
  });

  eventSource.addEventListener('error', (event: MessageEvent) => {
    if (event.data) {
      try {
        onError(JSON.parse(event.data).error || 'Unknown error');
      } catch {
        onError('Stream error');
      }
    } else {
      onError('Connection lost');
    }
    eventSource.close();
  });

  eventSource.onerror = () => {
    eventSource.close();
    onError('Connection to server lost');
  };

  return () => eventSource.close();
}

// ---------- File Upload ----------

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<{ source_id: number; filename: string; chunks_count: number; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/sources/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  });
  return res.data;
}

export async function clearUploads(): Promise<{ cleared_count: number; remaining_sources: number }> {
  const res = await api.post('/sources/clear-uploads');
  return res.data;
}

// ---------- Conversations ----------

export async function listConversations(): Promise<{ total: number; conversations: ConversationItem[] }> {
  const res = await api.get('/conversations');
  return res.data;
}

export async function createConversation(): Promise<ConversationItem> {
  const res = await api.post('/conversations');
  return res.data;
}

export async function getConversationMessages(conversationId: number): Promise<ChatMessageItem[]> {
  const res = await api.get(`/conversations/${conversationId}/messages`);
  return res.data;
}

export async function addMessage(conversationId: number, msg: {
  role: string;
  content: string;
  citations_json?: string[] | null;
  confidence?: string | null;
  latency_ms?: number | null;
  evidence_json?: EvidencePiece[] | null;
}): Promise<ChatMessageItem> {
  const res = await api.post(`/conversations/${conversationId}/messages`, msg);
  return res.data;
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await api.delete(`/conversations/${conversationId}`);
}

// ---------- Evidence & Sources ----------

export async function getEvidence(evidenceId: number): Promise<EvidencePiece> {
  const res = await api.get<EvidencePiece>(`/evidence/${evidenceId}`);
  return res.data;
}

export async function verifyAirgap(): Promise<AirgapResult> {
  return withRetry(async () => {
    const res = await api.get<AirgapResult>('/system/verify-airgap');
    return res.data;
  });
}

export async function listSources(): Promise<{ total: number; sources: SourceItem[] }> {
  const res = await api.get('/sources');
  return res.data;
}

export { withRetry };
export default api;
