export default function Loading(): React.ReactElement {
  return (
    <main className="centered-state" aria-live="polite">
      <div className="loading-mark" aria-hidden="true" />
      <p>Loading ShopFilter Eval…</p>
    </main>
  );
}
