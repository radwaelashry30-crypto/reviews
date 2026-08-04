import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useModelInfo, useModelStatus } from "../hooks/useAnalytics";

export function ModelInfoPage() {
  const status = useModelStatus();
  const info = useModelInfo();

  return (
    <div className="page">
      <h1>Model Information</h1>

      <section className="chart-card">
        <h2>Artifact Status</h2>
        {status.loading && <LoadingState />}
        <ErrorState error={status.error} />
        {status.data && (
          <table className="data-table">
            <thead><tr><th>Artifact</th><th>Status</th><th>Device</th></tr></thead>
            <tbody>
              {Object.entries(status.data.artifacts).map(([name, artifact]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{artifact.status}</td>
                  <td>{status.data!.device}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="chart-card">
        <h2>Label Mapping &amp; Limitations</h2>
        {info.loading && <LoadingState />}
        <ErrorState error={info.error} />
        {info.data && (
          <>
            <pre className="json-block">{JSON.stringify(info.data.label_mapping, null, 2)}</pre>
            <p className="limitations-note">{String(info.data.limitations)}</p>
          </>
        )}
      </section>
    </div>
  );
}
