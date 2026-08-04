import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { DeliveryChart, type StatePerformanceRow } from "../components/charts/DeliveryChart";
import { useStatePerformance } from "../hooks/useAnalytics";

export function GeographyPage() {
  const statePerf = useStatePerformance();

  return (
    <div className="page">
      <h1>Geography</h1>
      <section className="chart-card">
        <h2>Late-Delivery Rate by State (top offenders)</h2>
        {statePerf.loading && <LoadingState />}
        <ErrorState error={statePerf.error} />
        {statePerf.data && <DeliveryChart data={statePerf.data as unknown as StatePerformanceRow[]} />}
      </section>
    </div>
  );
}
