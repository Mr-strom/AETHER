import React, { useState } from 'react';
import { ChatPanel } from './components/ChatPanel';
import { QueryInput } from './components/QueryInput';
import { EvidenceCard } from './components/EvidenceCard';
import { ConflictGraph } from './components/ConflictGraph';
import { SystemStatusComponent } from './components/SystemStatus';
import { useStore } from './stores/useStore';
import { FilePlus, Database, Layers, Network, ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  const [rightTab, setRightTab] = useState<'evidence' | 'graph'>('evidence');
  const { sources } = useStore();

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* LEFT PANEL: Sources Sidebar */}
      <aside className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h1 className="font-bold text-base tracking-wide text-slate-100">AETHER</h1>
          </div>
          <span className="text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-800 px-1.5 py-0.5 rounded font-mono">
            RAG 1.0
          </span>
        </div>

        <div className="p-3 border-b border-slate-800">
          <button
            onClick={() => alert('File upload API endpoint is ready at /api/sources/upload.')}
            className="w-full flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold py-2 px-3 rounded-lg transition-colors shadow-sm"
          >
            <FilePlus className="w-4 h-4" /> Ingest Source File
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider px-1">
            <span>Evidence Sources</span>
            <span>({sources.length})</span>
          </div>

          {sources.length === 0 ? (
            <div className="text-center py-8 text-slate-500 text-xs px-2">
              <Database className="w-8 h-8 mx-auto mb-2 opacity-30" />
              No sources ingested yet. Upload PDFs, videos, or documents.
            </div>
          ) : (
            sources.map((src) => (
              <div
                key={src.id}
                className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg hover:border-slate-700 transition-colors text-xs space-y-1"
              >
                <div className="font-medium text-slate-200 truncate">{src.filename}</div>
                <div className="flex items-center justify-between text-[10px] text-slate-500">
                  <span className="uppercase">{src.file_type}</span>
                  <span className="text-emerald-400 capitalize">{src.status}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer status summary */}
        <div className="p-3 border-t border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Offline Local Engine</span>
          </div>
        </div>
      </aside>

      {/* CENTER PANEL: Main Chat Area */}
      <main className="flex-1 flex flex-col bg-slate-950 relative min-w-0">
        <header className="h-14 bg-slate-900/80 backdrop-blur border-b border-slate-800 px-6 flex items-center justify-between shrink-0">
          <div>
            <h2 className="font-semibold text-sm text-slate-200">Multimodal Evidence Reasoning Session</h2>
            <p className="text-xs text-slate-500">Offline RAG active across local indexed evidence store</p>
          </div>
        </header>

        <ChatPanel />

        <div className="p-4 bg-slate-950 border-t border-slate-800">
          <QueryInput />
        </div>
      </main>

      {/* RIGHT PANEL: Evidence Card & Conflict Graph */}
      <aside className="w-80 bg-slate-900 border-l border-slate-800 flex flex-col shrink-0">
        <div className="flex border-b border-slate-800 bg-slate-950">
          <button
            onClick={() => setRightTab('evidence')}
            className={`flex-1 py-3 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
              rightTab === 'evidence'
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-slate-900'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-3.5 h-3.5" /> Evidence Inspector
          </button>
          <button
            onClick={() => setRightTab('graph')}
            className={`flex-1 py-3 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
              rightTab === 'graph'
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-slate-900'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Network className="w-3.5 h-3.5" /> Conflict Graph
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <SystemStatusComponent />

          {rightTab === 'evidence' ? (
            <EvidenceCard />
          ) : (
            <ConflictGraph />
          )}
        </div>
      </aside>
    </div>
  );
};
