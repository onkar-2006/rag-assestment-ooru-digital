import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, Bot, User, ShieldAlert, Cpu, Sparkles, Zap, Layers, RefreshCw } from 'lucide-react';
import CitationBadge from './CitationBadge';

export default function ChatWorkspace({ messages, onSendMessage, onInspectCitation, isStreaming, promptSuggestions }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const getIntentBadge = (intent) => {
    switch (intent) {
      case 'greeting':
        return <span className="px-2 py-0.5 rounded-md bg-purple-950/80 border border-purple-800/60 text-purple-300 text-[10px] font-semibold">Conversational Bypass</span>;
      case 'structured_extraction':
        return <span className="px-2 py-0.5 rounded-md bg-amber-950/80 border border-amber-800/60 text-amber-300 text-[10px] font-semibold">Pydantic JSON Extraction</span>;
      case 'summarization':
        return <span className="px-2 py-0.5 rounded-md bg-cyan-950/80 border border-cyan-800/60 text-cyan-300 text-[10px] font-semibold">Section Map-Reduce Summary</span>;
      case 'cross_doc_comparison':
        return <span className="px-2 py-0.5 rounded-md bg-indigo-950/80 border border-indigo-800/60 text-indigo-300 text-[10px] font-semibold">Cross-Document Reasoning</span>;
      case 'blocked':
        return <span className="px-2 py-0.5 rounded-md bg-red-950/80 border border-red-800/60 text-red-300 text-[10px] font-semibold flex items-center gap-1"><ShieldAlert className="w-3 h-3"/> Security Violation Blocked</span>;
      default:
        return null;
    }
  };


  return (
    <div className="flex-1 h-full flex flex-col justify-between bg-black relative overflow-hidden">
      {/* Messages Scroll Feed */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6 my-auto pt-16">
            <div className="w-16 h-16 rounded-3xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-xl">
              <Bot className="w-8 h-8 text-cyan-400" />
            </div>
            <div className="space-y-3">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white">How can I assist your document research?</h2>
              <p className="text-sm sm:text-base text-slate-300 max-w-lg mx-auto leading-relaxed">
                Ask questions, request section summaries, extract structured JSON data, or compare multiple uploaded files side-by-side.
              </p>
            </div>

            {/* Quick Suggestion Chips */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 max-w-2xl w-full pt-4">
              {promptSuggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(suggestion.prompt)}
                  className="p-4.5 rounded-2xl bg-slate-900/80 hover:bg-slate-900 border border-slate-800 hover:border-cyan-500/60 text-left transition-all group cursor-pointer shadow-md"
                >
                  <div className="text-sm font-bold text-slate-100 group-hover:text-cyan-300 flex items-center justify-between">
                    <span>{suggestion.title}</span>
                    <Zap className="w-4 h-4 text-slate-400 group-hover:text-cyan-400" />
                  </div>
                  <div className="text-xs text-slate-400 font-medium mt-1.5 line-clamp-1">{suggestion.prompt}</div>
                </button>
              ))}
            </div>
          </div>

        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-3 sm:gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-white shrink-0 mt-1 shadow-md">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div className={`space-y-3 max-w-2xl ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                {/* Intent Tag & Meta */}
                {msg.role === 'assistant' && msg.intent && (
                  <div className="flex items-center gap-2">
                    {getIntentBadge(msg.intent)}
                    {msg.cached && (
                      <span className="px-2 py-0.5 rounded-md bg-slate-900 border border-slate-700 text-slate-400 text-[10px] font-mono">
                        ⚡ Cached (&lt;1ms)
                      </span>
                    )}
                  </div>
                )}

                {/* Message Content Bubble */}
                <div className={`p-4 sm:p-5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-lg rounded-tr-none'
                    : 'bg-slate-900/80 border border-slate-800/80 text-slate-200 glass-card rounded-tl-none'
                }`}>
                  {msg.role === 'user' ? (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  ) : (
                    <div className="prose prose-invert prose-slate max-w-none text-sm leading-relaxed">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  )}
                </div>

                {/* Citations List */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="pt-1 flex flex-wrap gap-2 items-center">
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Citations:</span>
                    {msg.citations.map((c, cIdx) => (
                      <CitationBadge key={cIdx} citation={c} onClick={onInspectCitation} />
                    ))}
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))
        )}

        {/* Streaming Loading State Indicator */}
        {isStreaming && (
          <div className="flex items-center gap-3 text-cyan-400 text-xs font-mono p-3 rounded-2xl bg-slate-900/60 border border-slate-800 w-fit">
            <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
            <span>Retrieving Hybrid Context &amp; Streaming Response...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box Footer */}
      <div className="p-4 sm:p-6 bg-slate-950/90 border-t border-slate-800/80 backdrop-blur-lg">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about your document, compare files, or request JSON extraction..."
            disabled={isStreaming}
            className="w-full py-4.5 pl-6 pr-16 rounded-2xl bg-slate-900 border border-slate-700/80 focus:border-cyan-500/80 text-slate-100 placeholder-slate-400 text-base font-medium focus:outline-none focus:ring-1 focus:ring-cyan-500/60 transition-all shadow-inner"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="absolute right-2.5 p-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:opacity-90 text-white disabled:opacity-40 transition-all cursor-pointer shadow-md"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>

    </div>
  );
}
