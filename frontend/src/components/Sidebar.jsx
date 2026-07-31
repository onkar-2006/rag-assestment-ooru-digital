import React from 'react';
import { FileText, Upload, Plus, Layers, ShieldCheck, Database, FileCheck } from 'lucide-react';

export default function Sidebar({ documents, activeSessionId, onUpload, onNewSession }) {
  return (
    <aside className="w-88 h-full bg-slate-950/95 border-r border-slate-800/80 flex flex-col justify-between p-5 glass-panel shrink-0 select-none">
      {/* Header & Logo */}
      <div className="space-y-6">
        <div className="flex items-center justify-between px-2 pt-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-white font-bold text-base shadow-md">
              AI
            </div>
            <div>
              <div className="text-base font-bold text-white tracking-wide">Document Intelligence</div>
            </div>
          </div>
        </div>

        {/* New Session Button */}
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2.5 py-3.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-sm font-bold text-white transition-all duration-200 shadow-md cursor-pointer hover:border-indigo-500/60"
        >
          <Plus className="w-5 h-5 text-indigo-400" />
          <span>New Session</span>
        </button>

        {/* Upload Trigger Drop Area */}
        <div className="relative group">
          <button
            type="button"
            onClick={onUpload}
            className="w-full flex flex-col items-center justify-center p-5 rounded-2xl border-2 border-dashed border-slate-700 group-hover:border-cyan-500/80 bg-slate-900/60 hover:bg-slate-900 transition-all cursor-pointer"
          >
            <Upload className="w-7 h-7 text-slate-400 group-hover:text-cyan-400 group-hover:scale-110 transition-all mb-1.5" />
            <span className="text-sm font-bold text-slate-200">Upload PDF / DOCX</span>
            <span className="text-xs text-slate-400 mt-1">Supports multi-document sessions</span>
          </button>
        </div>


        {/* Uploaded Documents List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-300 px-2 uppercase tracking-wider">
            <span>Session Documents ({documents.length})</span>
            <Layers className="w-4 h-4 text-slate-400" />
          </div>

          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {documents.length === 0 ? (
              <div className="p-4 text-center rounded-xl bg-slate-900/40 border border-slate-800/60 text-slate-400 text-sm font-medium italic">
                No documents uploaded yet.
              </div>
            ) : (
              documents.map((doc, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all"
                >
                  <FileText className="w-5 h-5 text-indigo-400 mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-slate-100 truncate">{doc.doc_name}</div>
                    <div className="flex items-center gap-2 text-xs text-slate-400 mt-1">
                      <span>{doc.total_pages} Pages</span>
                      <span>•</span>
                      <span>{doc.total_chunks} Chunks</span>
                    </div>
                  </div>
                  <FileCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}



