import React, { useRef, useState, useEffect } from 'react';
import { Sparkles, ArrowUp, Paperclip, AlertTriangle } from 'lucide-react';
import type { QueryResponse } from '../api/client';

interface Message {
  role: 'user' | 'aether';
  text: string;
  response?: QueryResponse;
}

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  onSubmit: (query: string) => void;
  onCitationClick: (eid: string) => void;
}

/** Parse answer text and render inline [EID-xxx] as clickable badges */
const renderAnswer = (
  text: string,
  onCitationClick: (eid: string) => void,
  confidence: string,
  conflicts: number,
) => {
  // Split by [EID-xxx] pattern
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
      {conflicts > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent-yellow/10 border border-accent-yellow/20">
          <AlertTriangle size={14} className="text-accent-yellow shrink-0" />
          <span className="text-xs text-accent-yellow font-body">
            ⚠️ {conflicts} conflict{conflicts > 1 ? 's' : ''} detected between sources
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
          // Handle line breaks and paragraphs
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
  onSubmit,
  onCitationClick,
}) => {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (trimmed && !isLoading) {
      onSubmit(trimmed);
      setInput('');
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full min-w-0">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-[720px] mx-auto space-y-6">
          {messages.map((msg, i) => (
            <div key={i} className="animate-fade-in">
              {msg.role === 'user' ? (
                /* User message */
                <div className="flex justify-end">
                  <div className="bg-aether-card border border-aether-border rounded-2xl rounded-tr-md px-4 py-3 max-w-[85%]">
                    <p className="text-sm text-gray-200 font-body">{msg.text}</p>
                  </div>
                </div>
              ) : (
                /* Aether response */
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
                          0, // conflicts count from response
                        )
                      : <p className="text-sm text-gray-300">{msg.text}</p>
                    }
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="animate-fade-in space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-primary animate-pulse-subtle" />
                <span className="text-sm font-headline font-semibold text-gray-300">
                  Aether
                </span>
              </div>
              <div className="pl-6 flex items-center gap-1.5">
                <div className="w-2 h-2 bg-primary/60 rounded-full animate-typing" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-primary/60 rounded-full animate-typing" style={{ animationDelay: '200ms' }} />
                <div className="w-2 h-2 bg-primary/60 rounded-full animate-typing" style={{ animationDelay: '400ms' }} />
                <span className="text-xs text-neutral ml-2 font-mono">Analyzing evidence...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Bottom input bar */}
      <div className="shrink-0 px-6 pb-4">
        <div className="max-w-[720px] mx-auto">
          <div className="relative flex items-center bg-aether-surface border border-aether-border rounded-xl overflow-hidden transition-all duration-300 focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20">
            <button className="pl-3 text-neutral hover:text-gray-400 transition-colors">
              <Paperclip size={16} />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
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
