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

export async function submitQuery(query: string): Promise<QueryResponse> {
  const res = await api.post<QueryResponse>('/query', { query });
  return res.data;
}

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
