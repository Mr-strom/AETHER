import React, { useState } from 'react';
import { BookOpen, FileText, File, FileSpreadsheet, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { EvidencePiece } from '../api/client';

interface SourcesPanelProps {
  evidence: EvidencePiece[];
  highlightedEid: string | null;
  isLoading?: boolean;
}

/** Get file type icon + color based on source name extension */
function getFileIcon(sourceName: string) {
  const ext = sourceName.split('.').pop()?.toLowerCase() || '';
  switch (ext) {
    case 'pdf': return { Icon: FileText, color: 'text-red-400', bg: 'bg-red-400/10' };
    case 'docx': case 'doc': return { Icon: FileText, color: 'text-blue-400', bg: 'bg-blue-400/10' };
    case 'csv': case 'xlsx': return { Icon: FileSpreadsheet, color: 'text-accent-green', bg: 'bg-accent-green/10' };
    case 'md': return { Icon: FileText, color: 'text-primary', bg: 'bg-primary/10' };
    default: return { Icon: File, color: 'text-neutral', bg: 'bg-neutral/10' };
  }
}

/** Collapsible evidence card */
const EvidenceCard: React.FC<{
  ev: EvidencePiece;
  isHighlighted: boolean;
  index: number;
}> = ({ ev, isHighlighted, index }) => {
  const [expanded, setExpanded] = useState(false);
  const eid = ev.metadata_json?.evidence_id || `EID-${ev.id}`;
  const sourceName = ev.metadata_json?.source_name || 'Unknown';
  const { Icon, color, bg } = getFileIcon(sourceName);
  const relevance = Math.round(ev.confidence_score * 100);
  const contentTruncated = ev.content?.length > 180;
  const displayContent = expanded
    ? ev.content
    : ev.content?.slice(0, 180) + (contentTruncated ? '...' : '');

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      id={`source-card-${eid.toUpperCase()}`}
      className={`
        rounded-xl border p-3.5 transition-all duration-300
        ${isHighlighted
          ? 'border-accent-blue/50 ring-1 ring-accent-blue/20 bg-accent-blue/5'
          : 'border-aether-border bg-aether-card hover:border-aether-hover'
        }
      `}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1 rounded ${bg}`}>
          <Icon size={12} className={color} />
        </div>
        <span className="text-xs text-gray-400 font-mono truncate flex-1">{sourceName}</span>
        <span className="eid-badge text-xxs shrink-0">{eid.toUpperCase()}</span>
      </div>

      {/* Relevance score */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 h-1 rounded-full bg-aether-border overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${relevance}%`,
              background: relevance >= 80 ? '#22C55E' : relevance >= 50 ? '#EAB308' : '#EF4444',
            }}
          />
        </div>
        <span className="text-xxs font-mono text-gray-500">{relevance}%</span>
      </div>

      {/* Content snippet */}
      <p className="text-xs text-gray-400 leading-relaxed font-body">
        {displayContent || <span className="italic text-neutral">No preview</span>}
      </p>

      {/* Expand/collapse toggle */}
      {contentTruncated && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 mt-2 text-xxs text-primary hover:text-primary-light transition-colors"
        >
          {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}

      {/* Page number */}
      {ev.page_number && (
        <div className="mt-1.5 text-xxs text-neutral font-mono">
          Page {ev.page_number}
        </div>
      )}
    </motion.div>
  );
};

const SourcesPanel: React.FC<SourcesPanelProps> = ({ evidence, highlightedEid, isLoading }) => {
  if (!evidence || evidence.length === 0) {
    return (
      <aside className="w-sources h-full bg-aether-surface border-l border-aether-border flex flex-col shrink-0">
        <div className="p-4 border-b border-aether-border flex items-center gap-2">
          <BookOpen size={16} className="text-gray-400" />
          <span className="text-sm font-headline font-semibold text-gray-200">Sources</span>
        </div>
        <div className="flex-1 flex items-center justify-center px-6">
          {isLoading ? (
            <div className="space-y-3 w-full">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse rounded-xl bg-aether-card border border-aether-border p-3.5">
                  <div className="h-3 bg-aether-border rounded w-3/4 mb-2" />
                  <div className="h-1 bg-aether-border rounded w-full mb-2" />
                  <div className="h-2 bg-aether-border rounded w-full mb-1" />
                  <div className="h-2 bg-aether-border rounded w-2/3" />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-neutral font-body text-center">
              Evidence sources will appear here when you ask a question.
            </p>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-sources h-full bg-aether-surface border-l border-aether-border flex flex-col shrink-0 overflow-hidden">
      <div className="p-4 border-b border-aether-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-gray-400" />
          <span className="text-sm font-headline font-semibold text-gray-200">Sources</span>
        </div>
        <span className="text-xs text-neutral font-mono">
          {evidence.length} ref{evidence.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        <AnimatePresence>
          {evidence.map((ev, i) => (
            <EvidenceCard
              key={ev.id}
              ev={ev}
              isHighlighted={highlightedEid === (ev.metadata_json?.evidence_id || `EID-${ev.id}`).toUpperCase()}
              index={i}
            />
          ))}
        </AnimatePresence>
      </div>
    </aside>
  );
};

export default SourcesPanel;
