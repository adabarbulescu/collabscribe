export async function shareDocumentLink(url, setToast) {
  try {
    await navigator.clipboard.writeText(url);
    setToast("Link copied to clipboard.");
  } catch {
    setToast("Could not copy the link.");
  }
}

export function exportAsMarkdown(content, docId, setToast) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `document-${docId}.md`;
  link.click();
  URL.revokeObjectURL(link.href);
  setToast("Markdown exported.");
}

export function exportAsPdf(docId, previewHtml, setToast) {
  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=960,height=720");
  if (!printWindow) {
    setToast("Popup blocked. Could not open PDF preview.");
    return;
  }

  printWindow.document.write(`
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <title>document-${docId}</title>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
        />
        <style>
          body {
            font-family: "Segoe UI", system-ui, sans-serif;
            margin: 32px auto;
            max-width: 860px;
            color: #20242b;
            line-height: 1.7;
            padding: 0 24px 40px;
          }
          pre {
            background: #f5f7fa;
            padding: 16px;
            border-radius: 12px;
            overflow: auto;
          }
          code {
            font-family: "Cascadia Code", monospace;
          }
          blockquote {
            margin: 0;
            padding-left: 16px;
            border-left: 3px solid #d4dbe6;
          }
        </style>
      </head>
      <body>${previewHtml}</body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  setToast("Print dialog opened for PDF export.");
}
