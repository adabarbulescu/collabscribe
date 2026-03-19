export default function Toast({ message }) {
  return (
    <div
      className={message ? "toast is-visible" : "toast"}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {message ?? ""}
    </div>
  );
}
