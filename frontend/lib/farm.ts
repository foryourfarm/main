import { authFetch } from "@/lib/auth";
import type {
  Crop,
  DashboardResponse,
  District,
  FarmCreated,
  FarmCreateInput,
  FarmMonthlyOutlook,
  FarmShortTerm,
  Region,
} from "@/types/farm";

// 장기 탭 조회. 인증 필수라 authFetch(Bearer + 401 시 refresh 1회) 경유.
// 계약: docs/long-term-tab-api.md.

export function fetchDashboard(): Promise<DashboardResponse> {
  return authFetch<DashboardResponse>("/api/v1/dashboard");
}

export function fetchMonthlyOutlook(farmId: number): Promise<FarmMonthlyOutlook> {
  return authFetch<FarmMonthlyOutlook>(`/api/v1/farms/${farmId}/monthly-outlook`);
}

export function fetchShortTerm(farmId: number): Promise<FarmShortTerm> {
  return authFetch<FarmShortTerm>(`/api/v1/farms/${farmId}/short-term`);
}

// 온보딩 선택지. regions/crops/districts는 공개 마스터지만 같은 래퍼로 통일한다.

export function fetchRegions(): Promise<Region[]> {
  return authFetch<Region[]>("/api/v1/regions");
}

export function fetchDistricts(regionId: number): Promise<District[]> {
  return authFetch<District[]>(`/api/v1/regions/${regionId}/districts`);
}

export function fetchCrops(): Promise<Crop[]> {
  return authFetch<Crop[]>("/api/v1/crops");
}

export function createFarm(input: FarmCreateInput): Promise<FarmCreated> {
  return authFetch<FarmCreated>("/api/v1/farms", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
