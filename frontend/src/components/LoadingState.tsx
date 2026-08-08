import { useEffect, useState } from "react";

/** After a few seconds, hints that the free-tier backend may be waking up
 * from an idle spin-down (can take up to ~50s) -- so a slow first request
 * reads as "expected", not "broken". */
export function LoadingState({ label = "Loading..." }: { label?: string }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="state state-loading">
      {label}
      {slow && <div className="state-loading-hint">Still working — the server may be waking up from idle (can take up to a minute on first load).</div>}
    </div>
  );
}
