import React, { useState, useEffect } from 'react';
import { ArrowRight, ShieldCheck, Cpu, Database, FileText } from 'lucide-react';

export default function WelcomeHero({ onEnter }) {
  const fullText = "Agentic Document Intelligence Assistant...";
  const [typedText, setTypedText] = useState("");
  const [isTypingComplete, setIsTypingComplete] = useState(false);

  useEffect(() => {
    let index = 0;
    const timer = setInterval(() => {
      if (index <= fullText.length) {
        setTypedText(fullText.slice(0, index));
        index++;
      } else {
        setIsTypingComplete(true);
        clearInterval(timer);
      }
    }, 60);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center justify-center bg-black bg-mesh-dark px-6 sm:px-12 py-16 overflow-hidden">
      {/* Background Ambient Glows */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-indigo-600/15 blur-[160px] rounded-full pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-cyan-500/10 blur-[140px] rounded-full pointer-events-none" />

      {/* Main Fullscreen Content Container */}
      <div className="relative z-10 max-w-5xl w-full text-center space-y-10">
        
        {/* Typewriter Header */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white min-h-[2.5em] flex items-center justify-center">
          <span className="bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent leading-tight">
            {typedText}
          </span>
          {!isTypingComplete && <span className="blinking-cursor" />}
        </h1>

        {/* Feature Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-4xl mx-auto py-6 border-y border-slate-800/80 text-left">
          <div className="flex items-center gap-3 p-4 rounded-2xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-md">
            <Cpu className="w-6 h-6 text-indigo-400 shrink-0" />
            <div>
              <div className="text-sm font-semibold text-slate-200">LangGraph Agent</div>
              <div className="text-xs text-slate-500">State Decision Graph</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-2xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-md">
            <Database className="w-6 h-6 text-cyan-400 shrink-0" />
            <div>
              <div className="text-sm font-semibold text-slate-200">Hybrid RRF RAG</div>
              <div className="text-xs text-slate-500">Dense + BM25 Search</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-2xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-md">
            <ShieldCheck className="w-6 h-6 text-emerald-400 shrink-0" />
            <div>
              <div className="text-sm font-semibold text-slate-200">Multi-Tier Safety</div>
              <div className="text-xs text-slate-500">Injection &amp; Guardrails</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-2xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-md">
            <FileText className="w-6 h-6 text-purple-400 shrink-0" />
            <div>
              <div className="text-sm font-semibold text-slate-200">Multi-Doc QA</div>
              <div className="text-xs text-slate-500">Cross-Doc Reasoning</div>
            </div>
          </div>
        </div>

        {/* CTA Launch Workspace Button */}
        <div className="pt-4">
          <button
            onClick={onEnter}
            className="group relative inline-flex items-center justify-center gap-3 px-10 py-5 rounded-2xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 text-white font-bold text-lg shadow-2xl hover:shadow-indigo-500/30 transition-all duration-300 transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer"
          >
            <span>Launch Workspace</span>
            <ArrowRight className="w-6 h-6 group-hover:translate-x-1.5 transition-transform" />
          </button>
        </div>

      </div>
    </div>
  );
}

