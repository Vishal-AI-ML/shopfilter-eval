"use client";

export default function ErrorPage({ reset }: { reset: () => void }): React.ReactElement {
  return (
    <main className="centered-state">
      <div className="state-card">
        <p className="eyebrow">SERVICE UNAVAILABLE</p>
        <h1>We could not load the workspace.</h1>
        <p>Confirm that the ShopFilter API is healthy, then try again.</p>
        <button className="primary-button" type="button" onClick={reset}>Try again</button>
      </div>
    </main>
  );
}
