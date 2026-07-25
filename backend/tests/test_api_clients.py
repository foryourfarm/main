"""API 클라이언트 실제 호출 테스트 (통합 검증).

weather_client.py + soil_chem_stat_client.py 실제 동작 검증.
"""

import sys
from datetime import datetime

# backend 모듈 경로 추가
sys.path.insert(0, "/C:/Users/User/Desktop/programming/AI_HACKATHON/backend")

from app.core.config import settings
from app.infra.public_api.weather_client import get_daily_weather
from app.infra.public_api.soil_chem_stat_client import get_region_soil_chem_stat


def test_weather_client():
    """기상청 sfc_aws_day.php 테스트."""
    print("\n" + "=" * 60)
    print("TEST 1: weather_client.py (KMA sfc_aws_day.php)")
    print("=" * 60)

    try:
        # 테스트: 서울 2025년 1월 최고기온
        print("\n[호출] 서울(108) 2025년 1월 최고기온")
        print("  - point_code: 108")
        print("  - start_date: 20250101")
        print("  - end_date: 20250131")
        print("  - obs_element: ta_max")

        result = get_daily_weather("108", "20250101", "20250131", "ta_max")

        print(f"\n[결과] ✅ 성공!")
        print(f"  - 조회된 일 수: {len(result)}")
        if result:
            print(f"  - 첫 번째 데이터:")
            first = result[0]
            print(f"    - 지점: {first.point_code}")
            print(f"    - 날짜: {first.obs_date}")
            print(f"    - 값: {first.obs_value}")
            print(f"  - 샘플 3개:")
            for i, obs in enumerate(result[:3]):
                print(f"    [{i+1}] {obs.obs_date}: {obs.obs_value}°C")

        return True

    except Exception as e:
        print(f"\n[오류] ❌ 실패!")
        print(f"  - 에러 타입: {type(e).__name__}")
        print(f"  - 메시지: {str(e)}")
        return False


def test_soil_chem_stat_client():
    """흙토람 화학성 통계 API 테스트."""
    print("\n" + "=" * 60)
    print("TEST 2: soil_chem_stat_client.py (흙토람 화학성)")
    print("=" * 60)

    try:
        # 테스트: 고창군 (5279000000)
        print("\n[호출] 고창군(5279000000) 화학성 통계")
        print("  - bjd_code: 5279000000")
        print("  - 엔드포인트:")
        print("    - getFarmExamPhInfo (pH)")
        print("    - getFarmExamOmInfo (유기물)")
        print("    - getFarmExamApInfo (유효인산)")

        result = get_region_soil_chem_stat("5279000000")

        if result:
            print(f"\n[결과] ✅ 성공!")
            print(f"  - 법정동코드: {result.bjd_code}")
            print(f"  - 법정동명: {result.bjd_name}")
            print(f"  - pH 평균: {result.ph_avg}")
            print(f"  - 유기물 평균: {result.organic_matter_avg}%")
            print(f"  - 유효인산 평균: {result.avail_p_avg} mg/kg")
            return True
        else:
            print(f"\n[결과] ⚠️ 데이터 없음 (None 반환)")
            return False

    except Exception as e:
        print(f"\n[오류] ❌ 실패!")
        print(f"  - 에러 타입: {type(e).__name__}")
        print(f"  - 메시지: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 테스트 실행."""
    print("\n" + "=" * 60)
    print("API 클라이언트 실제 호출 테스트 시작")
    print("=" * 60)
    print(f"시간: {datetime.now().isoformat()}")
    print(f"환경: {settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else 'local'}")

    results = {}

    # Test 1: weather_client
    results["weather_client"] = test_weather_client()

    # Test 2: soil_chem_stat_client
    results["soil_chem_stat"] = test_soil_chem_stat_client()

    # 최종 결과
    print("\n" + "=" * 60)
    print("최종 결과")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  - {test_name}: {status}")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\n총 {total_count}개 테스트 중 {passed_count}개 통과")

    if all(results.values()):
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패 - 위의 오류 메시지 확인")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
