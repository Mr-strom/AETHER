import React from 'react';
import { useStore } from '../stores/useStore';
import { FileText, Image, Mic, Film, Table as TableIcon } from 'lucide-react';
import { ModalityType } from '../types';

export const EvidenceCard: React.FC = () => {
  const { activeEvidence } = useStore();

  if (!activeEvidence) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm p-4 text-center">
        <FileText className="w-12 h-12 mb-2 opacity-30" />
        <p>Select an evidence chunk or click a reference citation to inspect details.</p>
      </div>
    );
  }

  const renderModalityIcon = (modality: ModalityType) => {
    switch (modality) {
      case 'image':
        return <Image className="w-4 h-4 text-emerald-400" />;
      case 'audio':
        return <Mic className="w-4 h-4 text-amber-400" />;
      case 'video':
        return <Film className="w-4 h-4 text-purple-400" />;
      case 'table':
        return <TableIcon className="w-4 h-4 text-cyan-400" />;
      default:
        return <FileText className="w-4 h-4 text-blue-400" />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3 text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          {renderModalityIcon(activeEvidence.modality)}
          <span className="font-semibold capitalize text-sm">{activeEvidence.modality} Evidence #{activeEvidence.id}</span>
        </div>
        <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-cyan-400 border border-slate-700">
          Conf: {(activeEvidence.confidence_score * 100).toFixed(0)}%
        </span>
      </div>

      <div className="bg-slate-950 p-3 rounded border border-slate-800 font-mono text-xs whitespace-pre-wrap max-h-64 overflow-y-auto">
        {activeEvidence.content}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 pt-2 border-t border-slate-800">
        <div>Chunk Index: #{activeEvidence.chunk_index}</div>
        <div>Source ID: #{activeEvidence.source_id}</div>
        {activeEvidence.page_number && <div>Page: {activeEvidence.page_number}</div>}
        {activeEvidence.timestamp_start !== undefined && (
          <div>Timestamp: {activeEvidence.timestamp_start}s - {activeEvidence.timestamp_end}s</div>
        )}
      </div>
    </div>
  );
};
