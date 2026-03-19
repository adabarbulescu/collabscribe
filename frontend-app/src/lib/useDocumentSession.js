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

export function useDocumentSession({ content, docId, onRestoreContent, onToast }) {
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaveAt, setLastSaveAt] = useState(null);
  const [userCount, setUserCount] = useState(1);

  useEffect(() => {
    let isMounted = true;

    async function restoreLatestVersion() {
      try {
        const response = await fetch(`/api/documents/${docId}/versions/latest`);
        if (response.status === 404) {
          return;
        }
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (!isMounted) {
          return;
        }

        if (data.created_at) {
          setLastSaveAt(data.created_at);
        }

        if (data.content && data.content.trim().length > 0) {
          onRestoreContent(data.content);
        }
      } catch (error) {
        if (isMounted) {
          onToast("Could not load the latest saved version.");
        }
      }
    }

    restoreLatestVersion();

    return () => {
      isMounted = false;
    };
  }, [docId, onRestoreContent, onToast]);

  useEffect(() => {
    const socket = io({
      transports: ["websocket", "polling"]
    });

    socket.on("connect", () => {
      setConnectionStatus("connected");
      socket.emit("join_room", { doc_id: docId });
    });

    socket.on("disconnect", () => {
      setConnectionStatus("disconnected");
    });

    socket.on("user_count", (data) => {
      setUserCount(data?.count ?? 1);
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
      setLastSaveAt(timestamp);
      onToast(`Version ${data.version_number} saved.`);
    } catch (error) {
      onToast(`Save failed: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  }

  return {
    connectionStatus,
    isSaving,
    lastSaveLabel: isSaving ? "Saving..." : formatLastSaveLabel(lastSaveAt),
    saveVersion,
    userCount
  };
}
