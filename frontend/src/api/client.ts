import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

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

// ---- Standard query (POST) ----

export async function submitQuery(query: string): Promise<QueryResponse> {
  const res = await api.post<QueryResponse>('/query', { query });
  return res.data;
}

// ---- SSE streaming query ----

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
      const data = JSON.parse(event.data) as StatusUpdate;
      onStatus(data);
    } catch { /* ignore parse errors */ }
  });

  eventSource.addEventListener('complete', (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as QueryResponse;
      onComplete(data);
    } catch { /* ignore */ }
    eventSource.close();
  });

  eventSource.addEventListener('error', (event: MessageEvent) => {
    if (event.data) {
      try {
        const data = JSON.parse(event.data);
        onError(data.error || 'Unknown error');
      } catch {
        onError('Stream error');
      }
    } else {
      onError('Connection lost');
    }
    eventSource.close();
  });

  eventSource.onerror = () => {
    // EventSource auto-reconnects; close explicitly if we get a persistent error
    eventSource.close();
    onError('Connection to server lost');
  };

  // Return cleanup function
  return () => eventSource.close();
}

// ---- File upload ----

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<{ source_id: number; filename: string; chunks_count: number; status: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await api.post('/sources/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });
  return res.data;
}

// ---- Clear uploads ----

export async function clearUploads(): Promise<{ cleared_count: number; remaining_sources: number }> {
  const res = await api.post('/sources/clear-uploads');
  return res.data;
}

// ---- Evidence & Sources ----

export async function getEvidence(evidenceId: number): Promise<EvidencePiece> {
  const res = await api.get<EvidencePiece>(`/evidence/${evidenceId}`);
  return res.data;
}

export async function verifyAirgap(): Promise<AirgapResult> {
  const res = await api.get<AirgapResult>('/system/verify-airgap');
  return res.data;
}

export async function listSources(): Promise<{ total: number; sources: SourceItem[] }> {
  const res = await api.get('/sources');
  return res.data;
}

export default api;
