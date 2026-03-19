import { useEffect, useState } from "react";
import { io } from "socket.io-client";

function formatLastSaveLabel(timestamp) {
  if (!timestamp) {
    return "Never";
  }

  const date = new Date(timestamp);
  return `Last: ${date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  })}`;
}

export function useDocumentSession({ content, docId, onToast }) {
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaveAt, setLastSaveAt] = useState(null);

  useEffect(() => {
    const socket = io({
      transports: ["websocket", "polling"]
    });

    socket.on("connect", () => {
      socket.emit("join_room", { doc_id: docId });
    });

    socket.on("autosave", (data) => {
      if (data?.doc_id === docId) {
        const now = new Date().toISOString();
        setLastSaveAt(now);
        onToast(`Autosaved version ${data.version_number}.`);
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [docId, onToast]);

  function noteSavedAt(timestamp) {
    setLastSaveAt(timestamp);
  }

  async function saveVersion() {
    if (isSaving) {
      return;
    }

    if (!content.trim()) {
      onToast("Cannot save an empty document.");
      return;
    }

    setIsSaving(true);

    try {
      const response = await fetch(`/api/documents/${docId}/versions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ content })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`);
      }

      const timestamp = data.created_at ?? new Date().toISOString();
      noteSavedAt(timestamp);
      onToast(`Version ${data.version_number} saved.`);
    } catch (error) {
      onToast(`Save failed: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  }

  return {
    isSaving,
    lastSaveLabel: isSaving ? "Saving..." : formatLastSaveLabel(lastSaveAt),
    noteSavedAt,
    saveVersion
  };
}
