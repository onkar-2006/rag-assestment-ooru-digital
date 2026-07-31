import React from 'react';
import { X, FileText, Layers, Hash, Sparkles } from 'lucide-react';

export default function CitationDrawer({ citation, onClose }) {
  if (!citation) return null;

  const percentage = Math.round((citation.similarity_score || citation.score || 0) * 100);

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-slate-950/95 border-l border-slate-800 p-6 glass-panel z-50 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-300">
      <div className="space-y-6">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Citation Inspector</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Match Percentage Card */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Relevance Match Score</div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400 font-mono">
              {percentage}%
            </span>
            <span className="text-xs text-slate-400">Hybrid Dense + BM25 RRF Rank</span>
          </div>
        </div>

        {/* Document Info */}
        <div className="space-y-4 text-xs">
          <div>
            <div className="text-slate-500 font-medium mb-1">Source Document</div>
            <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-200 font-semibold">
              <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
              <span className="truncate">{citation.doc_name}</span>
            </div>
          </div>

          <div>
            <div className="text-slate-500 font-medium mb-1">Section Breadcrumb Path</div>
            <div className="flex items-start gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-cyan-300 font-mono text-[11px] leading-relaxed">
              <Layers className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
              <span>{citation.section_path}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-slate-500 font-medium mb-1">Page Numbers</div>
              <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800 text-white font-mono text-center font-bold">
                {citation.page_numbers?.length ? citation.page_numbers.join(', ') : 'N/A'}
              </div>
            </div>

            <div>
              <div className="text-slate-500 font-medium mb-1">Chunk ID</div>
              <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-300 font-mono text-center truncate text-[11px]">
                {citation.chunk_id || 'N/A'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Close Action */}
      <button
        onClick={onClose}
        className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-white transition-colors cursor-pointer"
      >
        Done Inspecting
      </button>
    </div>
  );
}
