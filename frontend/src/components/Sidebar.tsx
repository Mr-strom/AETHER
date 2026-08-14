import React, { useState } from 'react';
import { Plus, FileText, Trash2 } from 'lucide-react';
import { clearUploads } from '../api/client';

export interface ChatHistoryItem {
  id: string;
  title: string;
  timestamp: string;
}

interface SidebarProps {
  isOpen: boolean;
  chatHistory: ChatHistoryItem[];
  activeChatId: string | null;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onUploadsCleared: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  chatHistory,
  activeChatId,
  onNewChat,
  onSelectChat,
  onUploadsCleared,
}) => {
  const [clearing, setClearing] = useState(false);

  const handleClearUploads = async () => {
    const confirmed = window.confirm(
      'This will remove all uploaded files and reset to demo data. Continue?'
    );
    if (!confirmed) return;

    setClearing(true);
    try {
      const result = await clearUploads();
      onUploadsCleared();
      // Optional: show result in console for debugging
      console.log(`Cleared ${result.cleared_count} uploads. ${result.remaining_sources} sources remain.`);
    } catch (err) {
      console.error('Clear uploads failed:', err);
    } finally {
      setClearing(false);
    }
  };

  return (
    <aside
      className={`
        h-full bg-aether-surface border-r border-aether-border
        flex flex-col shrink-0 transition-all duration-300 overflow-hidden z-20
        ${isOpen ? 'w-sidebar' : 'w-0'}
      `}
    >
      <div className="flex flex-col h-full p-3 min-w-[260px]">
        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg
                     bg-aether-card border border-aether-border
                     text-gray-300 text-sm font-body
                     hover:bg-aether-hover hover:border-primary/30
                     transition-all duration-200 mb-2"
        >
          <Plus size={16} className="text-primary" />
          <span>New Chat</span>
        </button>

        {/* Clear Uploads Button */}
        <button
          onClick={handleClearUploads}
          disabled={clearing}
          className="flex items-center gap-2 w-full px-3 py-1.5 rounded-lg
                     text-neutral text-xs font-mono
                     hover:bg-aether-card hover:text-accent-red
                     transition-all duration-200 mb-4
                     disabled:opacity-40"
        >
          <Trash2 size={12} />
          <span>{clearing ? 'Clearing...' : '🗑️ Clear Uploads'}</span>
        </button>

        {/* Past Chats */}
        <div className="flex-1 overflow-y-auto">
          <p className="text-xxs text-neutral uppercase tracking-wider font-mono px-2 mb-2">
            Past Chats
          </p>
          <div className="flex flex-col gap-0.5">
            {chatHistory.map((chat) => (
              <button
                key={chat.id}
                onClick={() => onSelectChat(chat.id)}
                className={`
                  flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left
                  text-sm font-body truncate transition-all duration-150
                  ${
                    activeChatId === chat.id
                      ? 'bg-aether-hover text-gray-200 border border-aether-border'
                      : 'text-gray-400 hover:bg-aether-card hover:text-gray-300 border border-transparent'
                  }
                `}
              >
                <FileText size={14} className="shrink-0 text-neutral" />
                <span className="truncate">{chat.title}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
