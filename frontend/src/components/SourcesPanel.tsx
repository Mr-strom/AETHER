import React from 'react';
import { FileText, BookOpen } from 'lucide-react';
import type { EvidencePiece } from '../api/client';

interface SourcesPanelProps {
  evidence: EvidencePiece[];
  highlightedEid: string | null;
}

/** Render content snippet with **bold** keyword highlighting */
const renderSnippet = (text: string, maxLen: number = 200) => {
  const truncated = text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
  const parts = truncated.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="text-gray-100 font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
};

const SourcesPanel: React.FC<SourcesPanelProps> = ({ evidence, highlightedEid }) => {
  if (!evidence || evidence.length === 0) {
    return (
      <aside className="w-sources h-full bg-aether-surface border-l border-aether-border flex flex-col shrink-0">
        <div className="p-4 border-b border-aether-border flex items-center gap-2">
          <BookOpen size={16} className="text-gray-400" />
          <span className="text-sm font-headline font-semibold text-gray-200">Sources</span>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-neutral font-body">No sources to display</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-sources h-full bg-aether-surface border-l border-aether-border flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-aether-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-gray-400" />
          <span className="text-sm font-headline font-semibold text-gray-200">Sources</span>
        </div>
        <span className="text-xs text-neutral font-mono">
          {evidence.length} Reference{evidence.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Evidence cards */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {evidence.map((ev) => {
          const eid = ev.metadata_json?.evidence_id || `EID-${ev.id}`;
          const sourceName = ev.metadata_json?.source_name || 'Unknown source';
          const isHighlighted = highlightedEid === eid.toUpperCase();

          return (
            <div
              key={ev.id}
              id={`source-card-${eid}`}
              className={`
                aether-card transition-all duration-300
                ${isHighlighted
                  ? 'border-accent-blue/50 ring-1 ring-accent-blue/20 bg-accent-blue/5'
                  : ''
                }
              `}
            >
              {/* Card header */}
              <div className="flex items-center gap-2 mb-2">
                <span className="eid-badge text-xxs">{eid.toUpperCase()}</span>
                <FileText size={12} className="text-neutral" />
                <span className="text-xs text-gray-400 font-mono truncate">{sourceName}</span>
              </div>

              {/* Content snippet */}
              <p className="text-xs text-gray-400 leading-relaxed font-body">
                {ev.content ? (
                  <>...{renderSnippet(ev.content)}</>
                ) : (
                  <span className="italic text-neutral">No content preview</span>
                )}
              </p>

              {/* Page number if available */}
              {ev.page_number && (
                <div className="mt-2 text-xxs text-neutral font-mono">
                  Page {ev.page_number}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
};

export default SourcesPanel;
