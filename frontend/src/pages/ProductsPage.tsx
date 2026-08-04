import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useCategoryPerformance } from "../hooks/useAnalytics";
import { formatCurrency } from "../utils/formatters";

export function ProductsPage() {
  const categories = useCategoryPerformance();

  return (
    <div className="page">
      <h1>Products</h1>
      <section className="chart-card">
        <h2>Top Categories by Item Revenue</h2>
        {categories.loading && <LoadingState />}
        <ErrorState error={categories.error} />
        {categories.data && (
          <table className="data-table">
            <thead><tr><th>Category</th><th>Item Revenue</th></tr></thead>
            <tbody>
              {categories.data.map((row) => (
                <tr key={String(row.product_category_name_english)}>
                  <td>{String(row.product_category_name_english)}</td>
                  <td>{formatCurrency(Number(row.price))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
