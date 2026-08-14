import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, MessageSquare, Clock } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  listConversations,
  createConversation,
  deleteConversation,
  clearUploads,
} from '../api/client';

export interface ChatHistoryItem {
  id: string;
  title: string;
  timestamp: string;
  dbId?: number; // database ID for real conversations
}

interface SidebarProps {
  isOpen: boolean;
  activeChatId: string | null;
  onNewChat: () => void;
  onSelectChat: (id: string, dbId?: number) => void;
  onUploadsCleared: () => void;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  activeChatId,
  onNewChat,
  onSelectChat,
  onUploadsCleared,
}) => {
  const [conversations, setConversations] = useState<ChatHistoryItem[]>([]);
  const [clearing, setClearing] = useState(false);

  // Load conversations from API on mount
  const loadConversations = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(
        data.conversations.map((c) => ({
          id: `conv-${c.id}`,
          title: c.title || 'New Chat',
          timestamp: timeAgo(c.updated_at),
          dbId: c.id,
        }))
      );
    } catch {
      // Backend may not be running yet
    }
  }, []);

  useEffect(() => {
    loadConversations();
    // Refresh every 30 seconds
    const interval = setInterval(loadConversations, 30000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  const handleNewChat = useCallback(async () => {
    try {
      const conv = await createConversation();
      const item: ChatHistoryItem = {
        id: `conv-${conv.id}`,
        title: 'New Chat',
        timestamp: 'Just now',
        dbId: conv.id,
      };
      setConversations((prev) => [item, ...prev]);
      onSelectChat(item.id, conv.id);
    } catch {
      // Fallback to local-only new chat
    }
    onNewChat();
  }, [onNewChat, onSelectChat]);

  const handleDelete = useCallback(async (e: React.MouseEvent, chatId: string, dbId?: number) => {
    e.stopPropagation();
    if (!dbId) return;
    try {
      await deleteConversation(dbId);
      setConversations((prev) => prev.filter((c) => c.id !== chatId));
    } catch {
      console.error('Failed to delete conversation');
    }
  }, []);

  const handleClearUploads = async () => {
    if (!window.confirm('Remove all uploaded files and reset to demo data?')) return;
    setClearing(true);
    try {
      await clearUploads();
      onUploadsCleared();
    } catch { /* ignore */ }
    setClearing(false);
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
        {/* New Chat */}
        <button
          onClick={handleNewChat}
          className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg
                     bg-aether-card border border-aether-border
                     text-gray-300 text-sm font-body
                     hover:bg-aether-hover hover:border-primary/30
                     transition-all duration-200 mb-2
                     focus:outline-none focus:ring-1 focus:ring-primary/30"
        >
          <Plus size={16} className="text-primary" />
          <span>New Chat</span>
        </button>

        {/* Clear Uploads */}
        <button
          onClick={handleClearUploads}
          disabled={clearing}
          className="flex items-center gap-2 w-full px-3 py-1.5 rounded-lg
                     text-neutral text-xs font-mono
                     hover:bg-aether-card hover:text-accent-red
                     transition-all duration-200 mb-4 disabled:opacity-40"
        >
          <Trash2 size={12} />
          <span>{clearing ? 'Clearing...' : '🗑️ Clear Uploads'}</span>
        </button>

        {/* Conversations */}
        <div className="flex-1 overflow-y-auto">
          <p className="text-xxs text-neutral uppercase tracking-wider font-mono px-2 mb-2">
            Conversations
          </p>
          <div className="flex flex-col gap-0.5">
            <AnimatePresence initial={false}>
              {conversations.map((chat) => (
                <motion.button
                  key={chat.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  onClick={() => onSelectChat(chat.id, chat.dbId)}
                  className={`
                    group flex items-center gap-2 w-full px-3 py-2 rounded-lg text-left
                    text-sm font-body transition-all duration-150
                    focus:outline-none focus:ring-1 focus:ring-primary/30
                    ${
                      activeChatId === chat.id
                        ? 'bg-aether-hover text-gray-200 border border-aether-border'
                        : 'text-gray-400 hover:bg-aether-card hover:text-gray-300 border border-transparent'
                    }
                  `}
                >
                  <MessageSquare size={14} className="shrink-0 text-neutral" />
                  <div className="flex-1 min-w-0">
                    <span className="block truncate text-xs">{chat.title}</span>
                    <span className="flex items-center gap-1 text-xxs text-neutral mt-0.5">
                      <Clock size={8} />
                      {chat.timestamp}
                    </span>
                  </div>
                  {chat.dbId && (
                    <button
                      onClick={(e) => handleDelete(e, chat.id, chat.dbId)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-accent-red/20 hover:text-accent-red transition-all"
                    >
                      <Trash2 size={10} />
                    </button>
                  )}
                </motion.button>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
