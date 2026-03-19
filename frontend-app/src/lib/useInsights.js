import { useEffect, useState } from "react";

export function useInsights({ docId, active, onToast }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!active || !docId) {
      return undefined;
    }

    const controller = new AbortController();

    async function loadInsights() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/documents/${docId}/insights?limit=60`, {
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
          onToast("Insights request failed.");
        }
      } finally {
        setIsLoading(false);
      }
    }

    loadInsights();

    return () => controller.abort();
  }, [active, docId, onToast]);

  return {
    data,
    error,
    isLoading
  };
}
