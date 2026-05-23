import { Activity, Send, MessageSquare, Plus, Clock } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  sendChatMessage,
  getChatSessions,
  getChatMessages
} from '../api/chatbotApi';

interface ChatbotPageProps {
  onBackToDashboard?: () => void;
}

export function ChatbotPage({ onBackToDashboard }: ChatbotPageProps) {
  const { appId } = useParams();
  const navigate = useNavigate();
  const [message, setMessage] = useState('');
  const [activeSessionId, setActiveSessionId] = useState(1);

  // Chat history sessions
 const [chatSessions, setChatSessions] = useState<any[]>([]);

type ChatMessage = { type: 'bot' | 'user'; content: string; details?: string };
const [messages, setMessages] = useState<ChatMessage[]>([
  {
    type: 'bot',
    content: 'Welcome to Chamora',
    details:
      "I'm your AI-powered assistant designed to help you with application performance analysis and provide intelligent recommendations, resolve edge case testing issues, optimize testing workflows, and much more."
  }
]);

const loadSessions = async () => {
  try {
    const response = await getChatSessions(appId || "1");
    setChatSessions(response.sessions || []);
  } catch (error) {
    console.error("Failed to load chat sessions", error);
  }
};

useEffect(() => {
  if (!appId) return;
    loadSessions();
}, [appId]);

const handleSend = async () => {
  if (!message.trim()) return;

  const userMessage = message;

  setMessages(prev => [
    ...prev,
    {
      type: 'user',
      content: userMessage
    }
  ]);

  setMessage('');

  try {
    const response = await sendChatMessage(
      appId || '1',
      userMessage
    );

    setMessages(prev => [
      ...prev,
      {
        type: 'bot',
        content: response.answer
      }
    ]);

    loadSessions();
  } catch (error) {
    console.error(error);

    setMessages(prev => [
      ...prev,
      {
        type: 'bot',
        content: 'Failed to connect to AI backend.'
      }
    ]);
  }
};

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Navigation Bar */}
      <nav className="bg-white/90 backdrop-blur-md border-b border-slate-200 px-6 py-4 shadow-md">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-6">
            <button
              onClick={() => {
                if (onBackToDashboard) {
                  onBackToDashboard();
                } else {
                  navigate(`/application/${appId}`);
                }
              }}
              className="flex items-center gap-3 hover:opacity-80 transition-opacity group"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div className="text-left">
                <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
                  Chamora
                </h1>
                <p className="text-xs text-slate-600 font-medium">AI Performance Intelligence Engine</p>
              </div>
            </button>
          </div>
          <div className="flex items-center gap-3 px-5 py-2.5 bg-gradient-to-r from-indigo-50 to-purple-50 border-2 border-indigo-200 rounded-xl shadow-sm">
            <span className="text-sm text-slate-700 font-medium">Current Mode:</span>
            <span className="font-bold text-indigo-700">Advisory</span>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-xs text-emerald-600 font-semibold">Active</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Chat Content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Left Sidebar - Chat History */}
        <div className="w-80 bg-white border-r border-slate-200 flex flex-col">
          {/* New Chat Button */}
          <div className="p-4 border-b border-slate-200">
            <button className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-br from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white rounded-lg transition-all shadow-md hover:shadow-lg font-semibold">
              <Plus className="w-5 h-5" />
              New Chat
            </button>
          </div>

          {/* Chat History List */}
          <div className="flex-1 overflow-y-auto p-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
              Chat History
            </h3>
            <div className="space-y-2">
              {chatSessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => setActiveSessionId(session.id)}
                  className={`w-full text-left p-3 rounded-lg transition-all ${
                    activeSessionId === session.id
                      ? 'bg-gradient-to-r from-indigo-50 to-purple-50 border-2 border-indigo-300 shadow-sm'
                      : 'bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <MessageSquare className={`w-4 h-4 mt-1 flex-shrink-0 ${
                      activeSessionId === session.id ? 'text-indigo-600' : 'text-slate-400'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className={`font-semibold text-sm truncate ${
                        activeSessionId === session.id ? 'text-indigo-700' : 'text-slate-800'
                      }`}>
                        {session.title}
                      </p>
                      <p className="text-xs text-slate-500 truncate mt-1">
                        {session.preview}
                      </p>
                      <div className="flex items-center gap-1 mt-2">
                        <Clock className="w-3 h-3 text-slate-400" />
                        <span className="text-xs text-slate-500">{session.timestamp}</span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 h-full">
          <div className="h-full bg-white/80 backdrop-blur-sm overflow-hidden flex flex-col">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-8">
              <div className="max-w-6xl mx-auto space-y-6">
                {messages.map((msg, index) => (
                  <div key={index} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-4xl ${
                      msg.type === 'user'
                        ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-2xl p-5 shadow-md'
                        : 'bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-indigo-200 rounded-2xl p-6 shadow-sm'
                    }`}>
                      {msg.type === 'bot' && (
                        <div>
                          <h3 className="font-bold text-xl text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 mb-3">
                            {msg.content}
                          </h3>
                          {msg.details && <p className="text-slate-700 leading-relaxed">{msg.details}</p>}
                        </div>
                      )}
                      {msg.type === 'user' && <p className="text-white">{msg.content}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Input Area */}
            <div className="border-t-2 border-slate-200 p-8 bg-gradient-to-r from-slate-50 to-blue-50">
              <div className="max-w-6xl mx-auto">
                <div className="flex gap-4 items-end">
                  <div className="flex-1 relative">
                    <textarea
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Send a message (Shift+Enter for new line)"
                      className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-xl px-5 py-4 text-slate-800 placeholder-slate-500 focus:outline-none focus:ring-4 focus:ring-indigo-100 resize-none shadow-sm transition-all"
                      rows={1}
                      style={{ minHeight: '56px', maxHeight: '150px' }}
                    />
                  </div>
                  <button
                    onClick={handleSend}
                    disabled={!message.trim()}
                    className="flex-shrink-0 bg-gradient-to-br from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:from-slate-300 disabled:to-slate-400 text-white px-6 py-4 rounded-xl transition-all shadow-md hover:shadow-xl disabled:cursor-not-allowed disabled:shadow-none hover:scale-105 active:scale-95"
                  >
                    <Send className="w-6 h-6" />
                  </button>
                </div>
                <div className="flex items-center justify-center gap-2 mt-4">
                  <div className="w-2 h-2 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full animate-pulse" />
                  <p className="text-sm text-slate-600 font-medium">
                    AI-powered assistance for performance analysis and testing optimization
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}