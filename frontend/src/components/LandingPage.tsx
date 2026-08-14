import React, { useState, useRef, useEffect } from 'react';
import { Terminal, ArrowUp, Upload } from 'lucide-react';
import { motion } from 'framer-motion';
import { AetherIcon, AetherWordmark } from './AetherLogo';
import { listSources } from '../api/client';

interface LandingPageProps {
  onSubmit: (query: string) => void;
  isLoading: boolean;
  onExit?: () => void;
}

const SUGGESTIONS_WITH_DOCS = [
  'Summarize the key findings across all documents',
  'Find any conflicting information between sources',
];

const SUGGESTIONS_WITHOUT_DOCS = [
  'Upload a document to get started',
];

const LandingPage: React.FC<LandingPageProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('');
  const [hasDocs, setHasDocs] = useState<boolean | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Check if documents exist
  useEffect(() => {
    listSources()
      .then((data) => setHasDocs(data.total > 0))
      .catch(() => setHasDocs(false));
  }, []);

  const handleSubmit = () => {
    const trimmed = query.trim();
    if (trimmed && !isLoading) onSubmit(trimmed);
  };

  const suggestions = hasDocs ? SUGGESTIONS_WITH_DOCS : SUGGESTIONS_WITHOUT_DOCS;

  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-aether-bg relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-[700px] h-[700px] rounded-full bg-primary/[0.03] blur-[150px]" />
      </div>

      {/* Logo group */}
      <motion.div
        className="relative z-10 flex flex-col items-center gap-4 mb-10"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      >
        <AetherIcon size={72} className="opacity-80" />
        <AetherWordmark large className="opacity-90" />
        <p className="text-neutral text-xs tracking-[0.3em] uppercase font-mono mt-1">
          Core Analytics Engine
        </p>
      </motion.div>

      {/* Onboarding message */}
      {hasDocs === false && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="relative z-10 flex items-center gap-3 px-5 py-3 rounded-xl bg-aether-surface border border-aether-border mb-6"
        >
          <Upload size={16} className="text-primary" />
          <div>
            <p className="text-sm text-gray-300 font-body">Drop your first document to get started</p>
            <p className="text-xs text-neutral font-mono mt-0.5">Supports PDF, DOCX, TXT, CSV, MD</p>
          </div>
        </motion.div>
      )}

      {/* Input bar */}
      <motion.div
        className="relative z-10 w-full max-w-[560px] px-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
      >
        <div className="relative flex items-center bg-aether-surface border border-aether-border rounded-xl overflow-hidden transition-all duration-300 focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20">
          <div className="pl-4 text-neutral">
            <Terminal size={16} />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder={hasDocs ? 'Ask anything about your documents...' : 'Upload documents first, then ask questions...'}
            className="flex-1 bg-transparent border-none outline-none px-3 py-3.5 text-sm text-gray-200 placeholder-neutral font-body"
            disabled={isLoading}
            autoFocus
          />
          <button
            onClick={handleSubmit}
            disabled={!query.trim() || isLoading}
            className="aether-btn-primary w-8 h-8 mr-2 shrink-0 disabled:opacity-30 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <ArrowUp size={16} />
            )}
          </button>
        </div>
      </motion.div>

      {/* Suggestion pills */}
      <motion.div
        className="relative z-10 flex items-center gap-3 mt-5 flex-wrap justify-center px-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.5 }}
      >
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => {
              if (!isLoading) { setQuery(suggestion); onSubmit(suggestion); }
            }}
            disabled={isLoading}
            className="px-4 py-2 rounded-full border border-aether-border bg-transparent
                       text-neutral text-xs font-body
                       hover:border-primary/40 hover:text-gray-300 hover:bg-aether-surface/50
                       transition-all duration-200 disabled:opacity-40
                       focus:outline-none focus:ring-1 focus:ring-primary/30"
          >
            {suggestion}
          </button>
        ))}
      </motion.div>
    </div>
  );
};

export default LandingPage;
