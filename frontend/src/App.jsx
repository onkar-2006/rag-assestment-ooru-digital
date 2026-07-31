import React, { useState, useEffect, useRef } from 'react';
import WelcomeHero from './components/WelcomeHero';
import Sidebar from './components/Sidebar';
import ChatWorkspace from './components/ChatWorkspace';
import CitationDrawer from './components/CitationDrawer';
import UploadingModal from './components/UploadingModal';
import RequiredUploadModal from './components/RequiredUploadModal';

export default function App() {
  const [hasEntered, setHasEntered] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [activeCitation, setActiveCitation] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // Uploading state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadingFileName, setUploadingFileName] = useState('');
  const [showUploadPromptModal, setShowUploadPromptModal] = useState(false);

  const handleEnterWorkspace = () => {
    setHasEntered(true);
    setShowUploadPromptModal(true);
  };


  // Hidden File Input Ref
  const fileInputRef = useRef(null);

  // Automatic Session Purge on Tab Close / Page Unload
  useEffect(() => {
    const handlePageUnload = () => {
      if (sessionId) {
        const payload = JSON.stringify({ session_id: sessionId });
        const blob = new Blob([payload], { type: 'application/json' });
        navigator.sendBeacon('/api/session/terminate', blob);
      }
    };

    window.addEventListener('pagehide', handlePageUnload);
    window.addEventListener('beforeunload', handlePageUnload);

    return () => {
      window.removeEventListener('pagehide', handlePageUnload);
      window.removeEventListener('beforeunload', handlePageUnload);
    };
  }, [sessionId]);

  const promptSuggestions = [
    { title: "Table Structure Model", prompt: "What AI model is used for table structure recognition?" },
    { title: "Extract JSON Metadata", prompt: "Extract key document metadata and metrics into JSON" },
    { title: "Summarize Pipeline", prompt: "Summarize Section 3 of the paper" },
    { title: "Cross-Doc Comparison", prompt: "Compare the key findings between document 1 and document 2" }
  ];

  // Trigger File Browser Dialog
  const triggerFileBrowser = () => {
    setShowUploadPromptModal(false);
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Handle Document Upload
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadingFileName(file.name);
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);
    
    // Pass session_id if appending to existing multi-doc session
    let url = '/api/documents/upload';
    if (sessionId) {
      url += `?session_id=${sessionId}`;
    }

    try {
      const res = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Upload failed');
      const data = await res.json();

      setSessionId(data.session_id);
      setDocuments((prev) => [...prev, {
        doc_name: data.doc_name,
        total_pages: data.total_pages,
        total_chunks: data.total_chunks
      }]);
      setShowUploadPromptModal(false);
    } catch (err) {
      alert(`Document Upload Failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      setUploadingFileName('');
      // Reset input value to allow re-uploading same file
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };


  // Handle New Session (Purges current session vectors before resetting state)
  const handleNewSession = async () => {
    if (sessionId) {
      try {
        await fetch('/api/session/terminate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId })
        });
      } catch (err) {
        console.warn("Failed to purge session on teardown:", err);
      }
    }

    setSessionId(null);
    setDocuments([]);
    setMessages([]);
    setActiveCitation(null);
  };


  // Handle Send Message & Token-by-Token SSE Streaming
  const handleSendMessage = async (userPrompt) => {
    if (!sessionId || documents.length === 0) {
      setShowUploadPromptModal(true);
      return;
    }

    // Add user message to trajectory
    setMessages((prev) => [...prev, { role: 'user', content: userPrompt }]);
    setIsStreaming(true);

    try {
      // Stream Response via Server-Sent Events (SSE)
      const eventSource = new EventSource(`/api/chat/stream?session_id=${sessionId}&message=${encodeURIComponent(userPrompt)}`);
      
      let assistantMsg = { role: 'assistant', content: '', citations: [], intent: 'document_qa' };
      
      // Append initial assistant placeholder message
      setMessages((prev) => [...prev, assistantMsg]);

      eventSource.addEventListener('token', (e) => {
        const data = JSON.parse(e.data);
        assistantMsg.content += data.token;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...assistantMsg };
          return updated;
        });
      });

      eventSource.addEventListener('citations', (e) => {
        const citations = JSON.parse(e.data);
        assistantMsg.citations = citations;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...assistantMsg };
          return updated;
        });
      });

      eventSource.addEventListener('done', () => {
        eventSource.close();
        setIsStreaming(false);
      });

      eventSource.onerror = (err) => {
        console.error("SSE Streaming error, closing stream:", err);
        eventSource.close();
        setIsStreaming(false);
      };
    } catch (err) {
      console.error("Chat error:", err);
      setIsStreaming(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-slate-100 font-sans flex flex-col antialiased">
      {/* Hidden File Input Element */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleUpload}
        accept=".pdf,.docx"
        className="hidden"
      />

      {!hasEntered ? (
        <WelcomeHero onEnter={handleEnterWorkspace} />
      ) : (

        <div className="h-screen w-screen flex overflow-hidden bg-black bg-mesh-dark animate-motion-enter">
          {/* Left Obsidian Sidebar */}
          <Sidebar
            documents={documents}
            activeSessionId={sessionId}
            onUpload={triggerFileBrowser}
            onNewSession={handleNewSession}
          />

          {/* Central Workspace Feed */}
          <ChatWorkspace
            messages={messages}
            onSendMessage={handleSendMessage}
            onInspectCitation={(c) => setActiveCitation(c)}
            isStreaming={isStreaming}
            promptSuggestions={promptSuggestions}
          />

          {/* Slide-Out Citation Inspector Drawer */}
          {activeCitation && (
            <CitationDrawer
              citation={activeCitation}
              onClose={() => setActiveCitation(null)}
            />
          )}

          {/* Document Ingestion Loader Modal */}
          <UploadingModal
            isOpen={isUploading}
            fileName={uploadingFileName}
          />

          {/* Required Document Upload Modal */}
          <RequiredUploadModal
            isOpen={showUploadPromptModal}
            onUploadClick={triggerFileBrowser}
          />
        </div>
      )}
    </div>
  );
}


