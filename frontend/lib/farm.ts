import { authFetch } from "@/lib/auth";
import type {
  Crop,
  DailyAdvice,
  DashboardResponse,
  District,
  Farm,
  FarmCreateInput,
  FarmMonthlyOutlook,
  FarmShortTerm,
  FarmUpdateInput,
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

/** 오늘의 행동추천. 단기 탭과 **따로** 부른다 — LLM 지연이 탭 렌더를 막지 않도록. */
export function fetchAdvice(farmId: number): Promise<DailyAdvice> {
  return authFetch<DailyAdvice>(`/api/v1/farms/${farmId}/advice`);
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

export function createFarm(input: FarmCreateInput): Promise<Farm> {
  return authFetch<Farm>("/api/v1/farms", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

// 설정 화면: 등록 정보 조회·수정·삭제.

export function fetchFarms(): Promise<Farm[]> {
  return authFetch<Farm[]>("/api/v1/farms");
}

export function updateFarm(farmId: number, input: FarmUpdateInput): Promise<Farm> {
  return authFetch<Farm>(`/api/v1/farms/${farmId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteFarm(farmId: number): Promise<string> {
  return authFetch<string>(`/api/v1/farms/${farmId}`, { method: "DELETE" });
}
