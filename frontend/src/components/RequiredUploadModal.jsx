import React from 'react';
import { UploadCloud, FileText, AlertCircle, ArrowUpRight } from 'lucide-react';

export default function RequiredUploadModal({ isOpen, onUploadClick }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-xl px-4 animate-modal-pop">
      <div className="relative w-full max-w-lg rounded-3xl bg-slate-950/90 border border-slate-800/80 p-8 shadow-2xl shadow-indigo-950/40 text-center space-y-6 overflow-hidden">
        {/* Glow Accent Effects */}
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-indigo-600/20 blur-3xl rounded-full pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-cyan-500/20 blur-3xl rounded-full pointer-events-none" />

        {/* Modal Header Icon */}
        <div className="relative z-10 mx-auto w-16 h-16 rounded-2xl bg-indigo-950/60 border border-indigo-500/30 flex items-center justify-center shadow-lg shadow-indigo-500/10">
          <UploadCloud className="w-8 h-8 text-indigo-400 animate-bounce" />
        </div>

        {/* Modal Text Heading & Body */}
        <div className="relative z-10 space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold">
            <AlertCircle className="w-3.5 h-3.5" />
            Document Required to Start
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Please Upload a Document First
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed max-w-md mx-auto">
            This is a specialized <span className="text-slate-200 font-semibold">Document Intelligence Engine</span>. Upload a <span className="text-cyan-400 font-mono text-xs">PDF</span>, <span className="text-cyan-400 font-mono text-xs">DOCX</span>, or <span className="text-cyan-400 font-mono text-xs">IMAGE</span> file to begin grounded QA, section summarization, or JSON extraction.
          </p>
        </div>

        {/* Primary Action Button */}
        <div className="relative z-10 pt-2">
          <button
            onClick={onUploadClick}
            className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white font-semibold text-base shadow-xl shadow-indigo-600/30 hover:shadow-indigo-500/40 transition-all transform hover:-translate-y-0.5 active:translate-y-0 flex items-center justify-center gap-2 cursor-pointer"
          >
            <FileText className="w-5 h-5 text-white" />
            <span>Select PDF / DOCX / Image</span>
            <ArrowUpRight className="w-5 h-5 opacity-80" />
          </button>
        </div>


        {/* Supported Formats Footnote */}
        <div className="relative z-10 text-xs text-slate-500 pt-1">
          Supports dense academic papers, multi-page contracts & reports
        </div>
      </div>
    </div>
  );
}
