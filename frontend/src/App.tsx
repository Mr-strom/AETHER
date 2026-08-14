import React, { useState, useCallback, useRef } from 'react';
import LandingPage from './components/LandingPage';
import TopBar from './components/TopBar';
import Sidebar, { ChatHistoryItem } from './components/Sidebar';
import ChatArea, { Message } from './components/ChatArea';
import SourcesPanel from './components/SourcesPanel';
import { ThinkingStep } from './components/ThinkingBubble';
import { streamQuery, EvidencePiece, QueryResponse, listSources } from './api/client';

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
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([
    { id: '1', title: 'Sector 7G Structural Integ...', timestamp: '2:45 AM' },
    { id: '2', title: 'Q3 Anomaly Reports Revi...', timestamp: '1:30 AM' },
    { id: '3', title: 'Maintenance Logs - Array ...', timestamp: '12:15 AM' },
  ]);
  const [activeChatId, setActiveChatId] = useState<string | null>('1');

  // Ref for SSE cleanup
  const cleanupRef = useRef<(() => void) | null>(null);

  const handleQuery = useCallback((query: string) => {
    setIsLoading(true);
    setView('chat');
    setThinkingSteps([]);
    setCurrentThinkingStep(null);

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', text: query }]);

    // Start SSE stream
    const cleanup = streamQuery(
      query,
      // onStatus
      (update) => {
        setCurrentThinkingStep(update.step);
        setThinkingSteps((prev) => {
          // Mark previous steps as completed
          const updated = prev.map((s) =>
            s.step !== update.step ? { ...s, completed: true } : s
          );
          // Add new step if not already present
          const exists = updated.find((s) => s.step === update.step);
          if (!exists) {
            updated.push({
              step: update.step,
              message: update.message,
              completed: false,
            });
          }
          return updated;
        });
      },
      // onComplete
      (response: QueryResponse) => {
        // Mark all thinking steps as complete
        setThinkingSteps((prev) => prev.map((s) => ({ ...s, completed: true })));
        setCurrentThinkingStep(null);

        // Add aether response message
        setMessages((prev) => [
          ...prev,
          { role: 'aether', text: response.answer, response },
        ]);

        // Update evidence panel
        setEvidence(response.evidence || []);

        // Update last query time
        const now = new Date();
        setLastQueryTime(
          now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
        );

        // Add to chat history
        const newChat: ChatHistoryItem = {
          id: Date.now().toString(),
          title: query.length > 30 ? query.slice(0, 30) + '...' : query,
          timestamp: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        };
        setChatHistory((prev) => [newChat, ...prev]);
        setActiveChatId(newChat.id);
        setIsLoading(false);
        setThinkingSteps([]);
      },
      // onError
      (error: string) => {
        setMessages((prev) => [
          ...prev,
          {
            role: 'aether',
            text: `Error: ${error}. Make sure the backend is running on port 8000.`,
          },
        ]);
        setIsLoading(false);
        setThinkingSteps([]);
        setCurrentThinkingStep(null);
      },
    );

    cleanupRef.current = cleanup;
  }, []);

  const handleNewChat = useCallback(() => {
    // Cancel any in-flight SSE stream
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
    setView('landing');
    setActiveChatId(null);
  }, []);

  const handleCitationClick = useCallback((eid: string) => {
    setHighlightedEid(eid);
    const el = document.getElementById(`source-card-${eid}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setTimeout(() => setHighlightedEid(null), 3000);
  }, []);

  const handleFilesUploaded = useCallback(() => {
    // Refresh sources list after upload
    listSources().then((data) => {
      // Evidence panel will update on next query
      console.log(`Sources updated: ${data.total} total`);
    }).catch(() => {});
  }, []);

  const handleUploadsCleared = useCallback(() => {
    // Reset evidence panel
    setEvidence([]);
    console.log('Uploads cleared');
  }, []);

  // LANDING VIEW
  if (view === 'landing') {
    return <LandingPage onSubmit={handleQuery} isLoading={isLoading} />;
  }

  // CHAT VIEW
  return (
    <div className="h-screen w-screen flex flex-col bg-aether-bg overflow-hidden">
      <TopBar
        onToggleSidebar={() => setSidebarOpen((p) => !p)}
        lastQueryTime={lastQueryTime}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          isOpen={sidebarOpen}
          chatHistory={chatHistory}
          activeChatId={activeChatId}
          onNewChat={handleNewChat}
          onSelectChat={setActiveChatId}
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
        />
        <SourcesPanel evidence={evidence} highlightedEid={highlightedEid} />
      </div>
    </div>
  );
};

export default App;
