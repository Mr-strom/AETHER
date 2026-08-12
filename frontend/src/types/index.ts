export type ModalityType = 'text' | 'image' | 'audio' | 'video' | 'table';

export interface Source {
  id: number;
  filename: str;
  file_type: str;
  file_path: str;
  file_hash: str;
  size_bytes: number;
  status: 'pending' | 'processing' | 'indexed' | 'error';
  metadata_json?: Record<string, any>;
  created_at: str;
  updated_at: str;
}

export interface EvidenceChunk {
  id: number;
  source_id: number;
  chunk_index: number;
  content: string;
  modality: ModalityType;
  page_number?: number;
  timestamp_start?: number;
  timestamp_end?: number;
  bbox_json?: Record<string, any>;
  embedding_id?: string;
  confidence_score: number;
  metadata_json?: Record<string, any>;
  created_at: string;
}

export interface EvidenceRelation {
  id: number;
  source_evidence_id: number;
  target_evidence_id: number;
  relation_type: 'supports' | 'contradicts' | 'elaborates' | 'temporally_follows';
  confidence: number;
  description?: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  timestamp: string;
  evidence?: EvidenceChunk[];
  confidence_score?: number;
  model_used?: string;
}

export interface SystemStatus {
  status: string;
  version: string;
  models_loaded: Array<{
    name: string;
    filename: string;
    size_mb: number;
    is_loaded: boolean;
    context_window: number;
  }>;
  ram_budget_mb: number;
  ram_usage_mb: number;
  gpu_layers: number;
  gpu_available: boolean;
  active_sources_count: number;
  total_evidence_chunks: number;
}

export interface GraphNodeData {
  id: string;
  label: string;
  group: string;
  evidence_id: number;
}

export interface GraphEdgeData {
  from: string;
  to: string;
  label: string;
  arrows?: string;
}

export interface ConflictGraphData {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
}
