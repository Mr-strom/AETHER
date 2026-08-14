import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Sparkles, ArrowUp, Paperclip, X, CheckCircle, Loader2, Square } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThinkingBubble, { ThinkingStep } from './ThinkingBubble';
import ConfidenceRing from './ConfidenceRing';
import { useTypewriter } from '../hooks/useTypewriter';
import type { QueryResponse } from '../api/client';
import { uploadFile } from '../api/client';

// ---------- Types ----------

interface Message {
  role: 'user' | 'aether';
  text: string;
  response?: QueryResponse;
  isNew?: boolean; // true for latest answer (enables typewriter)
}

interface UploadStatus {
  filename: string;
  state: 'uploading' | 'done' | 'error';
  progress: number;
  error?: string;
  chunks?: number;
}

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  thinkingSteps: ThinkingStep[];
  currentThinkingStep: string | null;
  onSubmit: (query: string) => void;
  onCitationClick: (eid: string) => void;
  onFilesUploaded: () => void;
  onStopGenerating?: () => void;
}

// ---------- Markdown components ----------

function MarkdownRenderer({ content, onCitationClick }: { content: string; onCitationClick: (eid: string) => void }) {
  // Pre-process: convert [EID-xxx] to markdown links for rendering
  const processed = content.replace(
    /\[(EID-\w+)\]/gi,
    (_, eid) => `[${eid.toUpperCase()}](#cite-${eid.toUpperCase()})`
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        strong: ({ children }) => (
          <strong className="text-gray-100 font-semibold">{children}</strong>
        ),
        em: ({ children }) => <em className="text-gray-300">{children}</em>,
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="list-none space-y-1 mb-2 ml-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal ml-5 space-y-1 mb-2">{children}</ol>,
        li: ({ children }) => (
          <li className="flex gap-2">
            <span className="text-primary mt-1.5 text-[6px]">●</span>
            <span className="flex-1">{children}</span>
          </li>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-2 rounded-lg border border-aether-border">
            <table className="w-full text-xs">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-aether-surface border-b border-aether-border">{children}</thead>
        ),
        th: ({ children }) => (
          <th className="px-3 py-2 text-left font-mono text-gray-300">{children}</th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 text-gray-400 border-t border-aether-border">{children}</td>
        ),
        code: ({ className, children }) => {
          const isBlock = className?.includes('language-');
          if (isBlock) {
            return (
              <div className="relative group my-2">
                <pre className="bg-aether-bg border border-aether-border rounded-lg p-3 overflow-x-auto text-xs">
                  <code className="font-mono text-gray-300">{children}</code>
                </pre>
                <button
                  onClick={() => navigator.clipboard.writeText(String(children))}
                  className="absolute top-2 right-2 px-2 py-0.5 rounded text-xxs bg-aether-border text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  Copy
                </button>
              </div>
            );
          }
          return (
            <code className="bg-aether-surface px-1.5 py-0.5 rounded text-xs font-mono text-primary-light">
              {children}
            </code>
          );
        },
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-primary pl-3 my-2 italic text-gray-400">
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => {
          // Citation links
          if (href?.startsWith('#cite-')) {
            const eid = href.replace('#cite-', '');
            return (
              <button
                onClick={() => onCitationClick(eid)}
                className="eid-badge mx-0.5 text-xxs inline-flex"
              >
                {eid}
              </button>
            );
          }
          return <a href={href} className="text-accent-blue hover:underline">{children}</a>;
        },
      }}
    >
      {processed}
    </ReactMarkdown>
  );
}

// ---------- Answer message with typewriter ----------

function AetherAnswer({ msg, onCitationClick }: {
  msg: Message;
  onCitationClick: (eid: string) => void;
}) {
  const { displayedText, isTyping, skipToEnd } = useTypewriter({
    text: msg.response?.answer || msg.text,
    speed: 15,
    enabled: msg.isNew === true,
  });

  const resp = msg.response;
  const conflicts = resp?.conflicts || [];
  const sourceCount = resp?.evidence?.length || 0;
  const latency = resp?.latency_ms ? (resp.latency_ms / 1000).toFixed(1) : null;

  return (
    <div className="space-y-2" onClick={isTyping ? skipToEnd : undefined}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-primary" />
        <span className="text-sm font-headline font-semibold text-gray-300">Aether</span>
        {resp && (
          <div className="ml-auto flex items-center gap-3">
            <ConfidenceRing confidence={resp.confidence} size={22} />
          </div>
        )}
      </div>

      {/* Answer body */}
      <div className="pl-6 text-sm text-gray-300 leading-relaxed font-body">
        <MarkdownRenderer content={displayedText} onCitationClick={onCitationClick} />
        {isTyping && <span className="text-primary animate-pulse">▌</span>}
      </div>

      {/* Metadata line */}
      {resp && !isTyping && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="pl-6 flex items-center gap-2 text-xxs text-neutral font-mono flex-wrap"
        >
          <span>Analyzed {sourceCount} source{sourceCount !== 1 ? 's' : ''}</span>
          <span className="text-aether-border">·</span>
          {conflicts.length > 0 && (
            <>
              <span className="text-accent-yellow">{conflicts.length} conflict{conflicts.length !== 1 ? 's' : ''}</span>
              <span className="text-aether-border">·</span>
            </>
          )}
          {latency && <span>{latency}s</span>}
        </motion.div>
      )}
    </div>
  );
}

// ---------- Main ChatArea ----------

const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isLoading,
  thinkingSteps,
  currentThinkingStep,
  onSubmit,
  onCitationClick,
  onFilesUploaded,
  onStopGenerating,
}) => {
  const [input, setInput] = useState('');
  const [uploads, setUploads] = useState<UploadStatus[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, thinkingSteps]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (trimmed && !isLoading) {
      onSubmit(trimmed);
      setInput('');
    }
  }, [input, isLoading, onSubmit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
    if (e.key === 'Escape' && isLoading && onStopGenerating) { onStopGenerating(); }
  }, [handleSubmit, isLoading, onStopGenerating]);

  // Ctrl+Enter global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleSubmit();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSubmit]);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const fileArray = Array.from(files);
    setUploads(fileArray.map((f) => ({ filename: f.name, state: 'uploading', progress: 0 })));

    let success = 0;
    for (const file of fileArray) {
      try {
        const result = await uploadFile(file, (p) => {
          setUploads((prev) => prev.map((u) => u.filename === file.name ? { ...u, progress: p } : u));
        });
        setUploads((prev) => prev.map((u) =>
          u.filename === file.name ? { ...u, state: 'done', progress: 100, chunks: result.chunks_count } : u
        ));
        success++;
      } catch (err: any) {
        setUploads((prev) => prev.map((u) =>
          u.filename === file.name ? { ...u, state: 'error', error: err?.response?.data?.detail || 'Failed' } : u
        ));
      }
    }
    setTimeout(() => setUploads([]), 4000);
    if (success > 0) onFilesUploaded();
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [onFilesUploaded]);

  return (
    <div className="flex-1 flex flex-col h-full min-w-0 relative">
      {/* Upload toasts */}
      <AnimatePresence>
        {uploads.length > 0 && (
          <div className="absolute top-4 right-4 z-50 flex flex-col gap-2">
            {uploads.map((u) => (
              <motion.div
                key={u.filename}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-aether-card border border-aether-border text-xs font-mono shadow-xl backdrop-blur"
              >
                {u.state === 'uploading' && <Loader2 size={12} className="text-accent-blue animate-spin" />}
                {u.state === 'done' && <CheckCircle size={12} className="text-accent-green" />}
                {u.state === 'error' && <X size={12} className="text-accent-red" />}
                <span className="text-gray-300 truncate max-w-[180px]">{u.filename}</span>
                {u.state === 'done' && <span className="text-accent-green">{u.chunks} chunks ✓</span>}
                {u.state === 'error' && <span className="text-accent-red truncate max-w-[100px]">{u.error}</span>}
              </motion.div>
            ))}
          </div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-[720px] mx-auto space-y-6">
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
              >
                {msg.role === 'user' ? (
                  <div className="flex justify-end">
                    <div className="bg-aether-card border border-aether-border rounded-2xl rounded-tr-md px-4 py-3 max-w-[85%]">
                      <p className="text-sm text-gray-200 font-body">{msg.text}</p>
                    </div>
                  </div>
                ) : (
                  <AetherAnswer msg={msg} onCitationClick={onCitationClick} />
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Thinking bubble */}
          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <ThinkingBubble steps={thinkingSteps} currentStep={currentThinkingStep} />
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Bottom input */}
      <div className="shrink-0 px-6 pb-4">
        <div className="max-w-[720px] mx-auto">
          {/* Stop generating button */}
          {isLoading && onStopGenerating && (
            <div className="flex justify-center mb-2">
              <button
                onClick={onStopGenerating}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-aether-border bg-aether-card text-xs text-gray-400 hover:text-gray-200 hover:border-primary/30 transition-all"
              >
                <Square size={10} className="fill-current" />
                Stop generating
              </button>
            </div>
          )}
          <div className="relative flex items-center bg-aether-surface border border-aether-border rounded-xl overflow-hidden transition-all duration-300 focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="pl-3 text-neutral hover:text-gray-300 transition-colors focus:outline-none focus:ring-1 focus:ring-primary/30 rounded"
              title="Upload files (PDF, DOCX, TXT, CSV, MD)"
              disabled={isLoading}
            >
              <Paperclip size={16} />
            </button>
            <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt,.csv,.md" multiple className="hidden" onChange={handleFileSelect} />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Aether..."
              className="flex-1 bg-transparent border-none outline-none px-3 py-3 text-sm text-gray-200 placeholder-neutral font-body"
              disabled={isLoading}
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isLoading}
              className="aether-btn-primary w-8 h-8 mr-2 shrink-0 disabled:opacity-30 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              <ArrowUp size={16} />
            </button>
          </div>
          <p className="text-center text-xxs text-neutral mt-2 font-mono">
            Ctrl+Enter to send · Esc to stop
          </p>
        </div>
      </div>
    </div>
  );
};

export type { Message };
export default ChatArea;
