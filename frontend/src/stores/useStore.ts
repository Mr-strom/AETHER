import { create } from 'zustand';
import { Source, EvidenceChunk, ChatMessage, SystemStatus, ConflictGraphData } from '../types';

interface AetherState {
  // Sources
  sources: Source[];
  activeSourceId: number | null;
  setSources: (sources: Source[]) => void;
  setActiveSourceId: (id: number | null) => void;

  // Chat
  messages: ChatMessage[];
  isQueryLoading: boolean;
  addMessage: (message: ChatMessage) => void;
  setQueryLoading: (loading: boolean) => void;

  // Evidence Viewer
  activeEvidence: EvidenceChunk | null;
  setActiveEvidence: (evidence: EvidenceChunk | null) => void;

  // System Status
  systemStatus: SystemStatus | null;
  setSystemStatus: (status: SystemStatus) => void;

  // Graph Data
  conflictGraph: ConflictGraphData;
  setConflictGraph: (graph: ConflictGraphData) => void;
}

export const useStore = create<AetherState>((set) => ({
  sources: [],
  activeSourceId: null,
  setSources: (sources) => set({ sources }),
  setActiveSourceId: (activeSourceId) => set({ activeSourceId }),

  messages: [
    {
      id: 'welcome',
      sender: 'assistant',
      content: 'Welcome to AETHER. Upload evidence sources or submit a query to get started.',
      timestamp: new Date().toLocaleTimeString(),
    },
  ],
  isQueryLoading: false,
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setQueryLoading: (isQueryLoading) => set({ isQueryLoading }),

  activeEvidence: null,
  setActiveEvidence: (activeEvidence) => set({ activeEvidence }),

  systemStatus: null,
  setSystemStatus: (systemStatus) => set({ systemStatus }),

  conflictGraph: { nodes: [], edges: [] },
  setConflictGraph: (conflictGraph) => set({ conflictGraph }),
}));
