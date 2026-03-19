import Editor from "@monaco-editor/react";
import { useCallback, useEffect, useRef } from "react";
import { MonacoBinding } from "y-monaco";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

function randomColor() {
  return `#${Math.floor(Math.random() * 0xffffff)
    .toString(16)
    .padStart(6, "0")}`;
}

export default function CollaborativeEditor({
  docId,
  initialContent,
  onConnectionStatusChange,
  onContentChange,
  onLastSaveAt,
  onToast,
  onUserCountChange
}) {
  const bindingRef = useRef(null);
  const editorRef = useRef(null);
  const providerRef = useRef(null);
  const ydocRef = useRef(null);
  const ytextRef = useRef(null);
  const cleanupRef = useRef(() => {});

  useEffect(() => {
    return () => {
      cleanupRef.current();
    };
  }, []);

  const handleMount = useCallback(
    async (editor) => {
      editorRef.current = editor;

      const ydoc = new Y.Doc();
      ydocRef.current = ydoc;

      const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${wsProto}//${window.location.host}/yjs`;
      const provider = new WebsocketProvider(wsUrl, docId, ydoc);
      providerRef.current = provider;

      const ytext = ydoc.getText("monaco");
      ytextRef.current = ytext;

      const awareness = provider.awareness;
      awareness.setLocalStateField("user", {
        color: randomColor(),
        name: `User-${Math.floor(Math.random() * 1000)}`
      });

      const binding = new MonacoBinding(
        ytext,
        editor.getModel(),
        new Set([editor]),
        awareness
      );
      bindingRef.current = binding;

      const syncPreview = () => {
        onContentChange(ytext.toString());
      };

      const updateUserCount = () => {
        onUserCountChange(Math.max(awareness.getStates().size, 1));
      };

      const handleProviderStatus = ({ status }) => {
        onConnectionStatusChange(status === "connected" ? "connected" : "disconnected");
      };

      const restoreLatestVersion = async () => {
        try {
          const response = await fetch(`/api/documents/${docId}/versions/latest`);
          if (response.status === 404) {
            if (ytext.toString().trim().length === 0 && initialContent.trim()) {
              ytext.insert(0, initialContent);
            }
            return;
          }

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }

          const data = await response.json();
          if (data.created_at) {
            onLastSaveAt(data.created_at);
          }

          if (ytext.toString().trim().length === 0) {
            const restored = data.content?.trim() ? data.content : initialContent;
            if (restored.trim()) {
              ytext.insert(0, restored);
            }
          }
        } catch (error) {
          onToast("Could not restore the latest saved version.");
          if (ytext.toString().trim().length === 0 && initialContent.trim()) {
            ytext.insert(0, initialContent);
          }
        }
      };

      const handleConnectedOnce = ({ status }) => {
        if (status !== "connected") {
          return;
        }
        provider.off("status", handleConnectedOnce);
        window.setTimeout(() => {
          void restoreLatestVersion();
        }, 500);
      };

      provider.on("status", handleProviderStatus);
      provider.on("status", handleConnectedOnce);
      awareness.on("change", updateUserCount);
      ytext.observe(syncPreview);

      syncPreview();
      updateUserCount();

      cleanupRef.current = () => {
        ytext.unobserve(syncPreview);
        awareness.off("change", updateUserCount);
        provider.off("status", handleProviderStatus);
        provider.off("status", handleConnectedOnce);
        binding.destroy();
        provider.destroy();
        ydoc.destroy();
      };
    },
    [
      docId,
      initialContent,
      onConnectionStatusChange,
      onContentChange,
      onLastSaveAt,
      onToast,
      onUserCountChange
    ]
  );

  return (
    <div className="editor-surface">
      <Editor
        defaultLanguage="markdown"
        defaultValue=""
        height="100%"
        onMount={handleMount}
        options={{
          automaticLayout: true,
          fontFamily: '"Cascadia Code", "Fira Code", "Consolas", monospace',
          fontSize: 14,
          lineNumbers: "on",
          minimap: { enabled: false },
          padding: { top: 12 },
          renderWhitespace: "none",
          scrollBeyondLastLine: false,
          tabSize: 2,
          theme: "vs-dark",
          wordWrap: "on"
        }}
        theme="vs-dark"
      />
    </div>
  );
}
