import { Activity, Send } from 'lucide-react';
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { sendChatMessage } from '../api/chatbotApi';
import ReactMarkdown from 'react-markdown';

interface ChatbotPageProps {
  onBackToDashboard?: () => void;
}

type ChatMessage = {
  type: 'bot' | 'user';
  content: string;
  details?: string;
};

export function ChatbotPage({ onBackToDashboard }: ChatbotPageProps) {
  const { appId } = useParams();
  const navigate = useNavigate();
  const [message, setMessage] = useState('');
  const [mode, setMode] = useState<'advisory' | 'diagnostic'>('advisory');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      type: 'bot',
      content: 'Welcome to Chamora',
      details:
        "I'm your AI-powered assistant designed to help you with application performance analysis and provide intelligent recommendations, resolve edge case testing issues, optimize testing workflows, and much more."
    }
  ]);

  const suggestedQuestions = [
    'How do I improve test coverage?',
    'What are the most critical test failures?',
    'Common Module Performance Data',
    'How to identify memory leaks and regular memory footprints?',
    'Optimize API response times across different environments',
    'Implement load/stress testing techniques',
    'Streamlined Error Handling: how to improve handling and error logging for better debugging',
  ];

  const handleSend = async () => {
    if (message.trim()) {
      const userMessage = message;

      setMessages(prev => [...prev, { type: 'user', content: userMessage }]);
      setMessage('');

      try {
        const response = await sendChatMessage(appId || '', userMessage);

        setMode(response.mode as 'advisory' | 'diagnostic');

        setMessages(prev => [
          ...prev,
          {
            type: 'bot',
            content: response.answer
          }
        ]);
      } catch (error) {
        setMessages(prev => [
          ...prev,
          {
            type: 'bot',
            content: 'Error: Failed to connect to AI backend.'
          }
        ]);
      }
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
                <p className="text-xs text-slate-600 font-medium">
                  AI Performance Intelligence Engine
                </p>
              </div>
            </button>
          </div>

          <div
            className={`flex items-center gap-3 px-5 py-2.5 border-2 rounded-xl shadow-sm ${
              mode === 'diagnostic'
                ? 'bg-gradient-to-r from-red-50 to-orange-50 border-red-200'
                : 'bg-gradient-to-r from-indigo-50 to-purple-50 border-indigo-200'
            }`}
          >
            <span className="text-sm text-slate-700 font-medium">Current Mode:</span>
            <span
              className={`font-bold ${
                mode === 'diagnostic' ? 'text-red-600' : 'text-indigo-700'
              }`}
            >
              {mode === 'diagnostic' ? 'Diagnostic' : 'Advisory'}
            </span>
            <div className="flex items-center gap-1">
              <div
                className={`w-2 h-2 rounded-full animate-pulse ${
                  mode === 'diagnostic' ? 'bg-red-500' : 'bg-emerald-500'
                }`}
              />
              <span
                className={`text-xs font-semibold ${
                  mode === 'diagnostic' ? 'text-red-600' : 'text-emerald-600'
                }`}
              >
                Active
              </span>
            </div>
          </div>
        </div>
      </nav>

      <div className="flex-1 overflow-hidden">
        <div className="h-full max-w-7xl mx-auto p-6">
          <div className="h-full bg-white/80 backdrop-blur-sm border-2 border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto p-6">
              <div className="max-w-5xl mx-auto space-y-6">
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-3xl ${
                        msg.type === 'user'
                          ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-2xl p-5 shadow-md'
                          : 'bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-indigo-200 rounded-2xl p-6 shadow-sm'
                      }`}
                    >
                    {msg.type === 'bot' && (
                    <div>
                      {msg.details ? (
                        <>
                          <h3 className="font-bold text-xl text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 mb-3">
                            {msg.content}
                          </h3>
                          <p className="text-slate-700 leading-relaxed">{msg.details}</p>
                        </>
                      ) : (
                        <div className="prose prose-slate max-w-none prose-p:leading-relaxed prose-li:leading-relaxed prose-strong:text-slate-800">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                  )}
                      {msg.type === 'user' && <p className="text-white">{msg.content}</p>}
                    </div>
                  </div>
                ))}

                {messages.length <= 1 && (
                  <div className="mt-8">
                    <div className="bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 border-2 border-indigo-200 rounded-2xl p-6 shadow-lg">
                      <div className="flex items-center gap-3 mb-5">
                        <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                          <span className="text-white font-bold">?</span>
                        </div>
                        <h3 className="font-bold text-lg text-slate-800">Popular Questions</h3>
                      </div>
                      <div className="grid grid-cols-1 gap-3">
                        {suggestedQuestions.slice(0, 8).map((question, index) => (
                          <button
                            key={index}
                            onClick={() => setMessage(question)}
                            className="group text-left bg-white hover:bg-gradient-to-r hover:from-indigo-50 hover:to-purple-50 border-2 border-slate-200 hover:border-indigo-300 px-5 py-4 rounded-xl transition-all shadow-sm hover:shadow-md"
                          >
                            <div className="flex items-start gap-3">
                              <span className="flex-shrink-0 w-6 h-6 bg-gradient-to-br from-indigo-100 to-purple-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold text-sm group-hover:scale-110 transition-transform">
                                {index + 1}
                              </span>
                              <span className="text-slate-700 group-hover:text-indigo-700 font-medium">
                                {question}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="border-t-2 border-slate-200 p-6 bg-gradient-to-r from-slate-50 to-blue-50">
              <div className="max-w-5xl mx-auto">
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