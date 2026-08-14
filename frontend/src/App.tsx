import React, { useState, useCallback } from 'react';
import LandingPage from './components/LandingPage';
import TopBar from './components/TopBar';
import Sidebar, { ChatHistoryItem } from './components/Sidebar';
import ChatArea, { Message } from './components/ChatArea';
import SourcesPanel from './components/SourcesPanel';
import { submitQuery, EvidencePiece } from './api/client';

type AppView = 'landing' | 'chat';

const App: React.FC = () => {
  const [view, setView] = useState<AppView>('landing');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [evidence, setEvidence] = useState<EvidencePiece[]>([]);
  const [highlightedEid, setHighlightedEid] = useState<string | null>(null);
  const [lastQueryTime, setLastQueryTime] = useState<string | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([
    { id: '1', title: 'Sector 7G Structural Integ...', timestamp: '2:45 AM' },
    { id: '2', title: 'Q3 Anomaly Reports Revi...', timestamp: '1:30 AM' },
    { id: '3', title: 'Maintenance Logs - Array ...', timestamp: '12:15 AM' },
  ]);
  const [activeChatId, setActiveChatId] = useState<string | null>('1');

  const handleQuery = useCallback(async (query: string) => {
    setIsLoading(true);
    setView('chat');

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', text: query }]);

    try {
      const response = await submitQuery(query);

      // Add aether response
      setMessages((prev) => [
        ...prev,
        {
          role: 'aether',
          text: response.answer,
          response,
        },
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
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || 'Query failed';
      setMessages((prev) => [
        ...prev,
        {
          role: 'aether',
          text: `Error: ${errMsg}. Make sure the backend is running on port 8000.`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setEvidence([]);
    setHighlightedEid(null);
    setView('landing');
    setActiveChatId(null);
  }, []);

  const handleCitationClick = useCallback((eid: string) => {
    setHighlightedEid(eid);
    // Scroll the source card into view
    const el = document.getElementById(`source-card-${eid}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    // Clear highlight after 3s
    setTimeout(() => setHighlightedEid(null), 3000);
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
        />
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          onSubmit={handleQuery}
          onCitationClick={handleCitationClick}
        />
        <SourcesPanel evidence={evidence} highlightedEid={highlightedEid} />
      </div>
    </div>
  );
};

export default App;
