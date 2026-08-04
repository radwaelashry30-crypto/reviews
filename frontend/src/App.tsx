import { Route, BrowserRouter, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GeographyPage } from "./pages/GeographyPage";
import { ModelInfoPage } from "./pages/ModelInfoPage";
import { ProductsPage } from "./pages/ProductsPage";
import { SellersPage } from "./pages/SellersPage";
import { SentimentPage } from "./pages/SentimentPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="sentiment" element={<SentimentPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="sellers" element={<SellersPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="geography" element={<GeographyPage />} />
          <Route path="model-info" element={<ModelInfoPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
