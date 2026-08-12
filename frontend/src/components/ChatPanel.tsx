import React, { useRef, useEffect } from 'react';
import { useStore } from '../stores/useStore';
import { Bot, User, CheckCircle2, ShieldAlert } from 'lucide-react';
import { EvidenceChunk } from '../types';

export const ChatPanel: React.FC = () => {
  const { messages, setActiveEvidence } = useStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          {msg.sender === 'assistant' && (
            <div className="w-8 h-8 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-cyan-400" />
            </div>
          )}

          <div
            className={`max-w-2xl rounded-2xl p-4 text-sm space-y-2 ${
              msg.sender === 'user'
                ? 'bg-cyan-600 text-white rounded-br-none'
                : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none'
            }`}
          >
            <div className="flex items-center justify-between gap-4 text-xs opacity-75 pb-1 border-b border-white/10">
              <span>{msg.sender === 'user' ? 'You' : 'AETHER Intelligence'}</span>
              <span>{msg.timestamp}</span>
            </div>

            <div className="leading-relaxed whitespace-pre-wrap">{msg.content}</div>

            {msg.sender === 'assistant' && (
              <div className="pt-2 flex flex-wrap items-center gap-2 text-xs">
                {msg.confidence_score !== undefined && (
                  <span className="flex items-center gap-1 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" />
                    {(msg.confidence_score * 100).toFixed(0)}% Factuality Score
                  </span>
                )}
                {msg.model_used && (
                  <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-slate-400 font-mono">
                    {msg.model_used}
                  </span>
                )}
              </div>
            )}

            {msg.evidence && msg.evidence.length > 0 && (
              <div className="mt-3 pt-2 border-t border-slate-800/80 space-y-1.5">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Citations & Evidence ({msg.evidence.length})</span>
                <div className="flex flex-wrap gap-1.5">
                  {msg.evidence.map((ev: EvidenceChunk, idx: number) => (
                    <button
                      key={ev.id || idx}
                      onClick={() => setActiveEvidence(ev)}
                      className="px-2 py-1 bg-slate-950 hover:bg-slate-800 text-cyan-400 text-xs rounded border border-slate-800 flex items-center gap-1 transition-colors"
                    >
                      [{idx + 1}] {ev.modality} chunk #{ev.chunk_index}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {msg.sender === 'user' && (
            <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
              <User className="w-4 h-4 text-slate-300" />
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
};
