import React, { useState } from 'react';
import { useStore } from '../stores/useStore';
import { sendQuery } from '../api/client';
import { Send, Loader2 } from 'lucide-react';

export const QueryInput: React.FC = () => {
  const [input, setInput] = useState('');
  const { addMessage, isQueryLoading, setQueryLoading } = useStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isQueryLoading) return;

    const userQuery = input.trim();
    setInput('');

    addMessage({
      id: Date.now().toString(),
      sender: 'user',
      content: userQuery,
      timestamp: new Date().toLocaleTimeString(),
    });

    setQueryLoading(true);

    try {
      const response = await sendQuery(userQuery);
      addMessage({
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        content: response.answer || 'Query processed.',
        timestamp: new Date().toLocaleTimeString(),
        confidence_score: response.confidence_score,
        model_used: response.model_used,
        evidence: response.evidence,
      });
    } catch (err: any) {
      addMessage({
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        content: `[Backend Processing Stub] Query sent: "${userQuery}". Full agentic RAG backend pipeline pending completion.`,
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setQueryLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative flex items-center">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask a question across your evidence repository..."
        className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 pr-12 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
      />
      <button
        type="submit"
        disabled={isQueryLoading || !input.trim()}
        className="absolute right-2 p-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:hover:bg-cyan-600 text-white transition-colors"
      >
        {isQueryLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
      </button>
    </form>
  );
};
