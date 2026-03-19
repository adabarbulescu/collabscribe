import { useEffect, useState } from "react";

export function useAnalytics({ content, docId, onToast }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!content.trim()) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/documents/${docId}/analytics`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ content }),
          signal: controller.signal
        });

        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        setData(payload);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
          onToast("Analytics request failed.");
        }
      } finally {
        setIsLoading(false);
      }
    }, 700);

    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [content, docId, onToast]);

  return {
    data,
    error,
    isLoading
  };
}
