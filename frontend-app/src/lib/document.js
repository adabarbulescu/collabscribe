export function getDocumentId(pathname) {
  const match = pathname.match(/\/doc\/([^/]+)/);
  return match?.[1] ?? "preview";
}
