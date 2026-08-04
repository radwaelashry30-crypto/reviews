import * as analyticsApi from "../api/analyticsApi";
import { useAsync } from "./useAsync";

export const useBusinessSummary = () => useAsync(analyticsApi.getBusinessSummary, []);
export const useMonthlyOrders = () => useAsync(analyticsApi.getMonthlyOrders, []);
export const useMonthlyRevenue = () => useAsync(analyticsApi.getMonthlyRevenue, []);
export const useReviewDistribution = () => useAsync(analyticsApi.getReviewDistribution, []);
export const useDeliverySummary = () => useAsync(analyticsApi.getDeliverySummary, []);
export const usePaymentDistribution = () => useAsync(analyticsApi.getPaymentDistribution, []);
export const useModelStatus = () => useAsync(analyticsApi.getModelStatus, []);
export const useModelInfo = () => useAsync(analyticsApi.getModelInfo, []);
export const useCustomerSummary = () => useAsync(analyticsApi.getCustomerSummary, []);
export const useTopCities = (n = 10) => useAsync(() => analyticsApi.getTopCities(n), [n]);
export const useSellerSummary = () => useAsync(analyticsApi.getSellerSummary, []);
export const useSellerPerformance = (n = 20) => useAsync(() => analyticsApi.getSellerPerformance(n), [n]);
export const useCategoryPerformance = () => useAsync(analyticsApi.getCategoryPerformance, []);
export const useStatePerformance = () => useAsync(analyticsApi.getStatePerformance, []);
