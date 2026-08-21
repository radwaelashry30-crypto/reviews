import { Route, BrowserRouter, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { BatchUploadPage } from "./pages/BatchUploadPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DesignSystemPreviewPage } from "./pages/DesignSystemPreviewPage";
import { GeographyPage } from "./pages/GeographyPage";
import { LandingPreviewPage } from "./pages/LandingPreviewPage";
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
          <Route path="batch-upload" element={<BatchUploadPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="sellers" element={<SellersPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="geography" element={<GeographyPage />} />
          <Route path="model-info" element={<ModelInfoPage />} />
        </Route>
        {/* Outside Layout on purpose: a temporary, unlinked Phase 1
            verification page, not part of the branded app shell. */}
        <Route path="design-system" element={<DesignSystemPreviewPage />} />
        {/* Phase 2 cinematic landing page -- staged at its own path per the
            routing-safety instructions. "/" keeps serving DashboardPage
            until this is promoted after visual approval. */}
        <Route path="landing-preview" element={<LandingPreviewPage />} />
      </Routes>
    </BrowserRouter>
  );
}
