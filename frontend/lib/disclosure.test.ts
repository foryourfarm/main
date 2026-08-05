import { describe, expect, it } from "vitest";
import { isFacilityIndicator, isReferenceTierScore } from "./disclosure";
import type { IndicatorBreakdown } from "@/types/farm";

describe("isFacilityIndicator", () => {
  it("시설 기준(facility)이면 true", () => {
    const b: IndicatorBreakdown = { cultivation_type: "facility" };
    expect(isFacilityIndicator(b)).toBe(true);
  });

  it("노지 기준(open_field)이면 false", () => {
    const b: IndicatorBreakdown = { cultivation_type: "open_field" };
    expect(isFacilityIndicator(b)).toBe(false);
  });

  it("null이면(지침에 미기재) false", () => {
    const b: IndicatorBreakdown = { cultivation_type: null };
    expect(isFacilityIndicator(b)).toBe(false);
  });

  it("필드 자체가 없으면(미채점 지표) false", () => {
    const b: IndicatorBreakdown = { status: "missing" };
    expect(isFacilityIndicator(b)).toBe(false);
  });
});

describe("isReferenceTierScore", () => {
  it("reference면 true", () => {
    const b: IndicatorBreakdown = { score_tier: "reference" };
    expect(isReferenceTierScore(b)).toBe(true);
  });

  it("literature면 false", () => {
    const b: IndicatorBreakdown = { score_tier: "literature" };
    expect(isReferenceTierScore(b)).toBe(false);
  });

  it("null이면(결속한 방향 없음, 예: optimal) false", () => {
    const b: IndicatorBreakdown = { score_tier: null };
    expect(isReferenceTierScore(b)).toBe(false);
  });

  it("필드 자체가 없으면(미채점 지표) false", () => {
    const b: IndicatorBreakdown = { status: "invalid" };
    expect(isReferenceTierScore(b)).toBe(false);
  });
});
