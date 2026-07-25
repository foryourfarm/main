import { authFetch } from "@/lib/auth";
import type { DashboardResponse, FarmMonthlyOutlook } from "@/types/farm";

// 장기 탭 조회. 인증 필수라 authFetch(Bearer + 401 시 refresh 1회) 경유.
// 계약: docs/long-term-tab-api.md.

export function fetchDashboard(): Promise<DashboardResponse> {
  return authFetch<DashboardResponse>("/api/v1/dashboard");
}

export function fetchMonthlyOutlook(farmId: number): Promise<FarmMonthlyOutlook> {
  return authFetch<FarmMonthlyOutlook>(`/api/v1/farms/${farmId}/monthly-outlook`);
}
