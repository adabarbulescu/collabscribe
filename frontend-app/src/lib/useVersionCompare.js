import { useEffect, useState } from "react";

function buildCompareUrl(docId, versionA, versionB) {
  const params = new URLSearchParams({
    v1: String(versionA),
    v2: String(versionB),
    include_analytics: "true"
  });

  return `/api/diff/${docId}/compare?${params.toString()}`;
}

export function useVersionCompare({ docId, active, onToast }) {
  const [versions, setVersions] = useState([]);
  const [selectedVersions, setSelectedVersions] = useState({ versionA: "", versionB: "" });
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState(null);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);

  useEffect(() => {
    if (!active || !docId) {
      return undefined;
    }

    const controller = new AbortController();

    async function loadVersions() {
      setIsLoadingVersions(true);
      setError(null);

      try {
        const response = await fetch(`/api/diff/${docId}/versions?limit=50`, {
          signal: controller.signal
        });
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        const nextVersions = payload.versions || [];
        setVersions(nextVersions);

        if (nextVersions.length >= 2) {
          setSelectedVersions((current) => {
            const available = new Set(nextVersions.map((version) => version.version_number));
            const latest = nextVersions[nextVersions.length - 1].version_number;
            const previous = nextVersions[nextVersions.length - 2].version_number;
            const currentA = available.has(current.versionA) ? current.versionA : previous;
            let currentB = available.has(current.versionB) ? current.versionB : latest;

            if (currentA === currentB) {
              currentB = currentB === latest ? previous : latest;
            }

            return { versionA: currentA, versionB: currentB };
          });
        } else {
          setSelectedVersions({ versionA: "", versionB: "" });
          setComparison(null);
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
          onToast("Version list request failed.");
        }
      } finally {
        setIsLoadingVersions(false);
      }
    }

    loadVersions();

    return () => controller.abort();
  }, [active, docId, onToast]);

  useEffect(() => {
    if (!active || !docId || !selectedVersions.versionA || !selectedVersions.versionB) {
      return undefined;
    }

    if (selectedVersions.versionA === selectedVersions.versionB) {
      return undefined;
    }

    const controller = new AbortController();

    async function loadComparison() {
      setIsLoadingComparison(true);
      setError(null);

      try {
        const response = await fetch(
          buildCompareUrl(docId, selectedVersions.versionA, selectedVersions.versionB),
          { signal: controller.signal }
        );
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        setComparison(payload);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
          onToast("Version comparison failed.");
        }
      } finally {
        setIsLoadingComparison(false);
      }
    }

    loadComparison();

    return () => controller.abort();
  }, [active, docId, onToast, selectedVersions.versionA, selectedVersions.versionB]);

  return {
    comparison,
    error,
    isLoading: isLoadingVersions || isLoadingComparison,
    selectedVersions,
    setSelectedVersions: (next) => {
      setSelectedVersions((current) => {
        const resolved = typeof next === "function" ? next(current) : next;

        if (!resolved.versionA || !resolved.versionB) {
          return resolved;
        }

        if (resolved.versionA !== resolved.versionB) {
          return resolved;
        }

        const alternatives = versions
          .map((version) => version.version_number)
          .filter((versionNumber) => versionNumber !== resolved.versionA);

        return {
          versionA: resolved.versionA,
          versionB: alternatives[alternatives.length - 1] ?? ""
        };
      });
    },
    versions
  };
}
