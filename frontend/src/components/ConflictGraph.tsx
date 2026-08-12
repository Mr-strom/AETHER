import React, { useEffect, useRef } from 'react';
import { Network } from 'vis-network';
import { useStore } from '../stores/useStore';

export const ConflictGraph: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { conflictGraph } = useStore();

  useEffect(() => {
    if (!containerRef.current) return;

    const data = {
      nodes: conflictGraph.nodes.length > 0 ? conflictGraph.nodes : [
        { id: '1', label: 'Source A (PDF)', group: 'source' },
        { id: '2', label: 'Chunk #101', group: 'evidence' },
        { id: '3', label: 'Chunk #204 (Contradiction)', group: 'conflict' },
      ],
      edges: conflictGraph.edges.length > 0 ? conflictGraph.edges : [
        { from: '1', to: '2', label: 'contains' },
        { from: '2', to: '3', label: 'contradicts', color: { color: '#ef4444' } },
      ],
    };

    const options = {
      nodes: {
        shape: 'dot',
        size: 16,
        font: { color: '#f8fafc', size: 12 },
      },
      edges: {
        color: { color: '#64748b' },
        font: { color: '#94a3b8', size: 10 },
      },
      physics: {
        enabled: true,
        barnesHut: { gravitationalConstant: -2000 },
      },
    };

    const network = new Network(containerRef.current, data, options);

    return () => {
      network.destroy();
    };
  }, [conflictGraph]);

  return (
    <div className="w-full h-64 bg-slate-950 border border-slate-800 rounded-lg overflow-hidden relative">
      <div className="absolute top-2 left-2 z-10 bg-slate-900/80 backdrop-blur px-2 py-1 rounded text-xs text-slate-300 border border-slate-800">
        Evidence Conflict Network
      </div>
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
};
