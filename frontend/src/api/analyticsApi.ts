import { apiGet } from "./client";
import type {
  BusinessSummary, CustomerSummary, DeliverySummary, ModelStatus, MonthlyOrderPoint, MonthlyRevenuePoint, SellerSummary, TopCity,
} from "../types/analytics";

export const getBusinessSummary = (): Promise<BusinessSummary> => apiGet("/analytics/summary");
export const getMonthlyOrders = (): Promise<MonthlyOrderPoint[]> => apiGet("/analytics/orders/monthly");
export const getMonthlyRevenue = (): Promise<MonthlyRevenuePoint[]> => apiGet("/analytics/revenue/monthly");
export const getReviewDistribution = (): Promise<Record<string, number>> => apiGet("/analytics/reviews/distribution");
export const getDeliverySummary = (): Promise<DeliverySummary> => apiGet("/analytics/delivery/summary");
export const getPaymentDistribution = (): Promise<Record<string, number>> => apiGet("/analytics/payments/distribution");

export const getModelStatus = (): Promise<ModelStatus> => apiGet("/models/status");
export const getModelInfo = (): Promise<Record<string, unknown>> => apiGet("/models/info");

export const getCustomerSummary = (): Promise<CustomerSummary> => apiGet("/customers/summary");
export const getTopCities = (n = 10): Promise<TopCity[]> => apiGet("/customers/top-cities", { n });

export const getSellerSummary = (): Promise<SellerSummary> => apiGet("/sellers/summary");
export const getSellerPerformance = (n = 20): Promise<Record<string, unknown>[]> => apiGet("/sellers/performance", { n });

export const getCategoryPerformance = (): Promise<Record<string, unknown>[]> => apiGet("/products/category-performance");
export const getStatePerformance = (): Promise<Record<string, unknown>[]> => apiGet("/geography/state-performance");
