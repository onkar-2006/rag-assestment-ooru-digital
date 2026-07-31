import React from 'react';
import { Sparkles, FileText, CheckCircle, Percent } from 'lucide-react';

export default function CitationBadge({ citation, onClick }) {
  const percentage = Math.round((citation.similarity_score || citation.score || 0) * 100);

  return (
    <button
      onClick={() => onClick(citation)}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 hover:border-cyan-500/60 text-xs text-slate-300 hover:text-white transition-all duration-200 cursor-pointer shadow-sm group"
    >
      <FileText className="w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition-transform" />
      <span className="font-medium max-w-[140px] truncate">{citation.doc_name}</span>
      <span className="text-slate-500 font-normal">|</span>
      <span className="inline-flex items-center font-mono text-[10px] font-semibold text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded">
        {percentage}% Match
      </span>
    </button>
  );
}
