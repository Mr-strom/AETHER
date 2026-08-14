import React, { useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import LandingPage from './components/LandingPage';
import TopBar from './components/TopBar';
import Sidebar from './components/Sidebar';
import ChatArea, { Message } from './components/ChatArea';
import SourcesPanel from './components/SourcesPanel';
import { ThinkingStep } from './components/ThinkingBubble';
import {
  streamQuery,
  EvidencePiece,
  QueryResponse,
  listSources,
  createConversation,
  addMessage,
  getConversationMessages,
} from './api/client';

type AppView = 'landing' | 'chat';

const App: React.FC = () => {
  const [view, setView] = useState<AppView>('landing');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [evidence, setEvidence] = useState<EvidencePiece[]>([]);
  const [highlightedEid, setHighlightedEid] = useState<string | null>(null);
  const [lastQueryTime, setLastQueryTime] = useState<string | null>(null);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [currentThinkingStep, setCurrentThinkingStep] = useState<string | null>(null);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [activeConvDbId, setActiveConvDbId] = useState<number | null>(null);

  const cleanupRef = useRef<(() => void) | null>(null);

  // Persist conversation to backend
  const ensureConversation = useCallback(async (): Promise<number | null> => {
    if (activeConvDbId) return activeConvDbId;
    try {
      const conv = await createConversation();
      setActiveConvDbId(conv.id);
      setActiveChatId(`conv-${conv.id}`);
      return conv.id;
    } catch {
      return null;
    }
  }, [activeConvDbId]);

  const handleQuery = useCallback(async (query: string) => {
    setIsLoading(true);
    setView('chat');
    setThinkingSteps([]);
    setCurrentThinkingStep(null);

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', text: query }]);

    // Persist user message
    const convId = await ensureConversation();
    if (convId) {
      addMessage(convId, { role: 'user', content: query }).catch(() => {});
    }

    const cleanup = streamQuery(
      query,
      (update) => {
        setCurrentThinkingStep(update.step);
        setThinkingSteps((prev) => {
          const updated = prev.map((s) =>
            s.step !== update.step ? { ...s, completed: true } : s
          );
          if (!updated.find((s) => s.step === update.step)) {
            updated.push({ step: update.step, message: update.message, completed: false });
          }
          return updated;
        });
      },
      (response: QueryResponse) => {
        setThinkingSteps((prev) => prev.map((s) => ({ ...s, completed: true })));
        setCurrentThinkingStep(null);

        setMessages((prev) => [
          ...prev,
          { role: 'aether', text: response.answer, response, isNew: true },
        ]);

        // Mark previous messages as not new (disable typewriter)
        setTimeout(() => {
          setMessages((prev) =>
            prev.map((m) => (m.isNew ? { ...m, isNew: false } : m))
          );
        }, 30000); // keep typewriter active for 30s max

        setEvidence(response.evidence || []);

        const now = new Date();
        setLastQueryTime(now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));

        // Persist aether response
        if (convId) {
          addMessage(convId, {
            role: 'aether',
            content: response.answer,
            citations_json: response.citations,
            confidence: response.confidence,
            latency_ms: response.latency_ms,
            evidence_json: response.evidence,
          }).catch(() => {});
        }

        setIsLoading(false);
        setThinkingSteps([]);
      },
      (error: string) => {
        // Friendly error messages
        let friendlyMsg: string;
        if (error.includes('Connection') || error.includes('connect')) {
          friendlyMsg = '🔌 Unable to reach the AETHER backend. Please ensure the server is running on port 8000.';
        } else if (error.includes('timeout') || error.includes('Timeout')) {
          friendlyMsg = '⏱️ The analysis is taking longer than expected. Please try a more specific question.';
        } else {
          friendlyMsg = `Something went wrong: ${error}`;
        }

        setMessages((prev) => [
          ...prev,
          { role: 'aether', text: friendlyMsg },
        ]);
        setIsLoading(false);
        setThinkingSteps([]);
        setCurrentThinkingStep(null);
      },
    );

    cleanupRef.current = cleanup;
  }, [ensureConversation]);

  const handleStopGenerating = useCallback(() => {
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
    setIsLoading(false);
    setThinkingSteps([]);
    setCurrentThinkingStep(null);
  }, []);

  const handleNewChat = useCallback(() => {
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
    setMessages([]);
    setEvidence([]);
    setHighlightedEid(null);
    setThinkingSteps([]);
    setCurrentThinkingStep(null);
    setIsLoading(false);
    setActiveConvDbId(null);
    setActiveChatId(null);
    setView('landing');
  }, []);

  const handleSelectChat = useCallback(async (id: string, dbId?: number) => {
    setActiveChatId(id);
    if (dbId) {
      setActiveConvDbId(dbId);
      try {
        const msgs = await getConversationMessages(dbId);
        setMessages(
          msgs.map((m) => ({
            role: m.role as 'user' | 'aether',
            text: m.content,
            response: m.role === 'aether' && m.evidence_json ? {
              query_id: 0,
              query: '',
              answer: m.content,
              citations: m.citations_json || [],
              confidence: m.confidence || 'medium',
              confidence_score: 0,
              response_time_ms: m.latency_ms || 0,
              latency_ms: m.latency_ms || 0,
              model_used: 'Qwen2.5-3B',
              evidence: m.evidence_json || [],
              created_at: m.created_at,
            } : undefined,
          }))
        );
        // Load evidence from last aether message
        const lastAether = msgs.filter((m) => m.role === 'aether').pop();
        if (lastAether?.evidence_json) {
          setEvidence(lastAether.evidence_json);
        }
        setView('chat');
      } catch {
        console.error('Failed to load conversation');
      }
    }
  }, []);

  const handleCitationClick = useCallback((eid: string) => {
    setHighlightedEid(eid);
    document.getElementById(`source-card-${eid}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => setHighlightedEid(null), 3000);
  }, []);

  const handleFilesUploaded = useCallback(() => {
    listSources().then((d) => console.log(`Sources: ${d.total}`)).catch(() => {});
  }, []);

  const handleUploadsCleared = useCallback(() => {
    setEvidence([]);
  }, []);

  // LANDING VIEW
  if (view === 'landing') {
    return (
      <AnimatePresence mode="wait">
        <motion.div
          key="landing"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.4 }}
        >
          <LandingPage onSubmit={handleQuery} isLoading={isLoading} />
        </motion.div>
      </AnimatePresence>
    );
  }

  // CHAT VIEW
  return (
    <motion.div
      key="chat"
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="h-screen w-screen flex flex-col bg-aether-bg overflow-hidden"
    >
      <TopBar
        onToggleSidebar={() => setSidebarOpen((p) => !p)}
        lastQueryTime={lastQueryTime}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          isOpen={sidebarOpen}
          activeChatId={activeChatId}
          onNewChat={handleNewChat}
          onSelectChat={handleSelectChat}
          onUploadsCleared={handleUploadsCleared}
        />
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          thinkingSteps={thinkingSteps}
          currentThinkingStep={currentThinkingStep}
          onSubmit={handleQuery}
          onCitationClick={handleCitationClick}
          onFilesUploaded={handleFilesUploaded}
          onStopGenerating={handleStopGenerating}
        />
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          <SourcesPanel evidence={evidence} highlightedEid={highlightedEid} isLoading={isLoading} />
        </motion.div>
      </div>
    </motion.div>
  );
};

export default App;
