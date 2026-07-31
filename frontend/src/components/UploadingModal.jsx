import React from 'react';
import { Loader2, FileText, Cpu, Database, Sparkles } from 'lucide-react';

export default function UploadingModal({ isOpen, fileName }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative max-w-md w-full glass-panel p-8 rounded-3xl border border-slate-800 text-center space-y-6 shadow-2xl neon-glow-indigo">
        
        {/* Animated Pulsing Outer Ring & Loader */}
        <div className="relative w-24 h-24 mx-auto flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-4 border-indigo-500/20 animate-ping" />
          <div className="absolute inset-0 rounded-full border-4 border-t-cyan-400 border-r-indigo-500 border-b-purple-500 border-l-transparent animate-spin" />
          <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner">
            <FileText className="w-8 h-8 text-cyan-400 animate-pulse" />
          </div>
        </div>

        {/* Processing Title */}
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-900 border border-slate-700/80 text-xs font-semibold text-cyan-400 uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 animate-spin" />
            <span>Document Pipeline Ingestion</span>
          </div>
          <h3 className="text-xl font-extrabold text-white">Processing Document...</h3>
          <p className="text-sm text-slate-300 font-medium truncate max-w-xs mx-auto">
            {fileName || 'Uploading document...'}
          </p>
        </div>

        {/* Pipeline Stage Indicators */}
        <div className="space-y-2.5 pt-2 border-t border-slate-800/80 text-left text-xs font-medium">
          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
            <Loader2 className="w-4 h-4 text-cyan-400 animate-spin shrink-0" />
            <span className="text-slate-200">Stage 1: Structural PDF/DOCX Layout Parsing</span>
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
            <Cpu className="w-4 h-4 text-indigo-400 shrink-0" />
            <span className="text-slate-400">Stage 2: Section Breadcrumbs &amp; Table Chunker</span>
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
            <Database className="w-4 h-4 text-purple-400 shrink-0" />
            <span className="text-slate-400">Stage 3: Qdrant Cloud Vector Indexing</span>
          </div>
        </div>

      </div>
    </div>
  );
}
