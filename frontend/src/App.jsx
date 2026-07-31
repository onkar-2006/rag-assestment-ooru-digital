import React, { useState } from 'react';
import WelcomeHero from './components/WelcomeHero';
import Sidebar from './components/Sidebar';
import ChatWorkspace from './components/ChatWorkspace';
import CitationDrawer from './components/CitationDrawer';
import UploadingModal from './components/UploadingModal';

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

  const promptSuggestions = [
    { title: "Table Structure Model", prompt: "What AI model is used for table structure recognition?" },
    { title: "Extract JSON Metadata", prompt: "Extract key document metadata and metrics into JSON" },
    { title: "Summarize Pipeline", prompt: "Summarize Section 3 of the paper" },
    { title: "Cross-Doc Comparison", prompt: "Compare the key findings between document 1 and document 2" }
  ];

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
    } catch (err) {
      alert(`Document Upload Failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      setUploadingFileName('');
    }
  };


  // Handle New Session
  const handleNewSession = () => {
    setSessionId(null);
    setDocuments([]);
    setMessages([]);
    setActiveCitation(null);
  };

  // Handle Send Message & Token-by-Token SSE Streaming
  const handleSendMessage = async (userPrompt) => {
    if (!sessionId) {
      alert("Please upload a document (.pdf or .docx) first to start your research session.");
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
      {!hasEntered ? (
        <WelcomeHero onEnter={() => setHasEntered(true)} />
      ) : (
        <div className="h-screen w-screen flex overflow-hidden bg-black bg-mesh-dark">
          {/* Left Obsidian Sidebar */}
          <Sidebar
            documents={documents}
            activeSessionId={sessionId}
            onUpload={handleUpload}
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
        </div>
      )}
    </div>
  );

}
