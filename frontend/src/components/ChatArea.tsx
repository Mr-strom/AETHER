import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Sparkles, ArrowUp, Paperclip, AlertTriangle, X, CheckCircle, Loader2 } from 'lucide-react';
import ThinkingBubble, { ThinkingStep } from './ThinkingBubble';
import type { QueryResponse } from '../api/client';
import { uploadFile } from '../api/client';

interface Message {
  role: 'user' | 'aether';
  text: string;
  response?: QueryResponse;
}

interface UploadStatus {
  filename: string;
  state: 'uploading' | 'processing' | 'done' | 'error';
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
}

/** Parse answer text and render inline [EID-xxx] as clickable badges */
const renderAnswer = (
  text: string,
  onCitationClick: (eid: string) => void,
  confidence: string,
  conflicts: string[],
) => {
  const parts = text.split(/(\[EID-\w+\])/gi);

  return (
    <div className="space-y-3">
      {/* Confidence badge */}
      <div className="flex items-center gap-2 mb-1">
        <div
          className={`w-2 h-2 rounded-full ${
            confidence === 'high'
              ? 'bg-accent-green'
              : confidence === 'medium'
              ? 'bg-accent-yellow'
              : 'bg-accent-red'
          }`}
        />
        <span className={`text-xs font-mono ${
          confidence === 'high'
            ? 'confidence-high'
            : confidence === 'medium'
            ? 'confidence-medium'
            : 'confidence-low'
        }`}>
          {confidence} confidence
        </span>
      </div>

      {/* Conflict banner */}
      {conflicts.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent-yellow/10 border border-accent-yellow/20">
          <AlertTriangle size={14} className="text-accent-yellow shrink-0" />
          <span className="text-xs text-accent-yellow font-body">
            ⚠️ {conflicts.length} conflict{conflicts.length > 1 ? 's' : ''} detected between sources
          </span>
        </div>
      )}

      {/* Answer text with inline citations */}
      <div className="text-sm text-gray-300 leading-relaxed font-body">
        {parts.map((part, i) => {
          const match = part.match(/^\[(EID-\w+)\]$/i);
          if (match) {
            const eid = match[1].toUpperCase();
            return (
              <button
                key={i}
                onClick={() => onCitationClick(eid)}
                className="eid-badge mx-0.5 text-xxs"
              >
                {eid}
              </button>
            );
          }
          return (
            <span key={i}>
              {part.split('\n').map((line, j, arr) => (
                <React.Fragment key={j}>
                  {renderBoldText(line)}
                  {j < arr.length - 1 && <br />}
                </React.Fragment>
              ))}
            </span>
          );
        })}
      </div>
    </div>
  );
};

/** Render **bold** markdown text */
const renderBoldText = (text: string) => {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="text-gray-100 font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
};

const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isLoading,
  thinkingSteps,
  currentThinkingStep,
  onSubmit,
  onCitationClick,
  onFilesUploaded,
}) => {
  const [input, setInput] = useState('');
  const [uploads, setUploads] = useState<UploadStatus[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, thinkingSteps]);

  const handleSubmit = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const trimmed = input.trim();
    if (trimmed && !isLoading) {
      debounceRef.current = setTimeout(() => {
        onSubmit(trimmed);
        setInput('');
      }, 50);
    }
  }, [input, isLoading, onSubmit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  // File upload handler
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);
    const newUploads: UploadStatus[] = fileArray.map((f) => ({
      filename: f.name,
      state: 'uploading' as const,
      progress: 0,
    }));
    setUploads((prev) => [...prev, ...newUploads]);

    let successCount = 0;

    for (let i = 0; i < fileArray.length; i++) {
      const file = fileArray[i];
      try {
        // Update to uploading
        setUploads((prev) => prev.map((u) =>
          u.filename === file.name ? { ...u, state: 'uploading' } : u
        ));

        const result = await uploadFile(file, (percent) => {
          setUploads((prev) => prev.map((u) =>
            u.filename === file.name ? { ...u, progress: percent } : u
          ));
        });

        // Update to done
        setUploads((prev) => prev.map((u) =>
          u.filename === file.name
            ? { ...u, state: 'done', progress: 100, chunks: result.chunks_count }
            : u
        ));
        successCount++;
      } catch (err: any) {
        const errMsg = err?.response?.data?.detail || err?.message || 'Upload failed';
        setUploads((prev) => prev.map((u) =>
          u.filename === file.name
            ? { ...u, state: 'error', error: errMsg }
            : u
        ));
      }
    }

    // Clear upload statuses after 4 seconds
    setTimeout(() => setUploads([]), 4000);

    // Notify parent to refresh sources
    if (successCount > 0) {
      onFilesUploaded();
    }

    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [onFilesUploaded]);

  return (
    <div className="flex-1 flex flex-col h-full min-w-0">
      {/* Upload status toast */}
      {uploads.length > 0 && (
        <div className="absolute top-16 right-[380px] z-50 flex flex-col gap-2 animate-slide-up">
          {uploads.map((u, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-aether-card border border-aether-border text-xs font-mono shadow-lg"
            >
              {u.state === 'uploading' && (
                <Loader2 size={12} className="text-accent-blue animate-spin" />
              )}
              {u.state === 'processing' && (
                <Loader2 size={12} className="text-primary animate-spin" />
              )}
              {u.state === 'done' && (
                <CheckCircle size={12} className="text-accent-green" />
              )}
              {u.state === 'error' && (
                <X size={12} className="text-accent-red" />
              )}
              <span className="text-gray-300 truncate max-w-[200px]">{u.filename}</span>
              {u.state === 'uploading' && (
                <span className="text-neutral">{u.progress}%</span>
              )}
              {u.state === 'done' && u.chunks !== undefined && (
                <span className="text-accent-green">{u.chunks} chunks ✓</span>
              )}
              {u.state === 'error' && (
                <span className="text-accent-red truncate max-w-[120px]">{u.error}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-[720px] mx-auto space-y-6">
          {messages.map((msg, i) => (
            <div key={i} className="animate-fade-in">
              {msg.role === 'user' ? (
                <div className="flex justify-end">
                  <div className="bg-aether-card border border-aether-border rounded-2xl rounded-tr-md px-4 py-3 max-w-[85%]">
                    <p className="text-sm text-gray-200 font-body">{msg.text}</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Sparkles size={16} className="text-primary" />
                    <span className="text-sm font-headline font-semibold text-gray-300">
                      Aether
                    </span>
                    {msg.response && (
                      <span className="text-xxs text-neutral font-mono ml-auto">
                        {msg.response.latency_ms}ms
                      </span>
                    )}
                  </div>
                  <div className="pl-6">
                    {msg.response
                      ? renderAnswer(
                          msg.response.answer,
                          onCitationClick,
                          msg.response.confidence,
                          msg.response.conflicts || [],
                        )
                      : <p className="text-sm text-gray-300">{msg.text}</p>
                    }
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Thinking bubble (SSE steps) */}
          {isLoading && (
            <ThinkingBubble steps={thinkingSteps} currentStep={currentThinkingStep} />
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Bottom input bar */}
      <div className="shrink-0 px-6 pb-4">
        <div className="max-w-[720px] mx-auto">
          <div className="relative flex items-center bg-aether-surface border border-aether-border rounded-xl overflow-hidden transition-all duration-300 focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20">
            {/* Paperclip — wired to file picker */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="pl-3 text-neutral hover:text-gray-300 transition-colors"
              title="Upload files"
              disabled={isLoading}
            >
              <Paperclip size={16} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.csv,.md"
              multiple
              className="hidden"
              onChange={handleFileSelect}
            />
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
              className="aether-btn-primary w-8 h-8 mr-2 shrink-0 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export type { Message };
export default ChatArea;
