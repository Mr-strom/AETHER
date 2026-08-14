import React, { useState, useRef } from 'react';
import { Terminal, ArrowUp } from 'lucide-react';
import { AetherIcon, AetherWordmark } from './AetherLogo';

interface LandingPageProps {
  onSubmit: (query: string) => void;
  isLoading: boolean;
}

const SUGGESTIONS = [
  'Analyze recent corpus anomalies',
  'Audit system security protocols',
];

const LandingPage: React.FC<LandingPageProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    const trimmed = query.trim();
    if (trimmed && !isLoading) {
      onSubmit(trimmed);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit();
  };

  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-aether-bg relative overflow-hidden">
      {/* Subtle background glow */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-[600px] h-[600px] rounded-full bg-primary/5 blur-[120px]" />
      </div>

      {/* Logo */}
      <div className="relative z-10 flex flex-col items-center gap-4 mb-10 animate-fade-in">
        <AetherIcon size={72} className="opacity-80" />
        <AetherWordmark large className="opacity-90" />
        <p className="text-neutral text-xs tracking-[0.3em] uppercase font-mono mt-1">
          Core Analytics Engine
        </p>
      </div>

      {/* Input bar */}
      <div className="relative z-10 w-full max-w-[560px] px-6 animate-slide-up">
        <div className="relative flex items-center bg-aether-surface border border-aether-border rounded-xl overflow-hidden transition-all duration-300 focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20">
          <div className="pl-4 text-neutral">
            <Terminal size={16} />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Aether a question..."
            className="flex-1 bg-transparent border-none outline-none px-3 py-3.5 text-sm text-gray-200 placeholder-neutral font-body"
            disabled={isLoading}
            autoFocus
          />
          <button
            onClick={handleSubmit}
            disabled={!query.trim() || isLoading}
            className="aether-btn-primary w-8 h-8 mr-2 shrink-0 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <ArrowUp size={16} />
            )}
          </button>
        </div>
      </div>

      {/* Suggestion pills */}
      <div className="relative z-10 flex items-center gap-3 mt-5 animate-slide-up" style={{ animationDelay: '100ms' }}>
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => {
              if (!isLoading) {
                setQuery(suggestion);
                onSubmit(suggestion);
              }
            }}
            disabled={isLoading}
            className="px-4 py-2 rounded-full border border-aether-border bg-transparent
                       text-neutral text-xs font-body
                       hover:border-primary/40 hover:text-gray-300 hover:bg-aether-surface/50
                       transition-all duration-200 disabled:opacity-40"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
};

export default LandingPage;
