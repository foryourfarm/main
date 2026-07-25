"""crop_growth_guide 문헌 기반 기준값 반영 (LoopReport.md, 기온강수량-문헌정리.md)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-25

문헌 조사 결과를 시드에 반영하고, 기존 행에도 근거·신뢰도를 채운다.

**넣지 않은 값과 이유** (문헌이 명시적으로 경고했거나 미확정 — 추측으로 채우지 않는다):
- 배 일소 47.1℃: **과실표면온도(FST)**이지 대기온이 아니다. temp_day에 넣으면 심각한
  오류가 된다(LoopReport "FST vs 대기온 분리 필요").
- 사과 강수 120/319/113mm: LoopReport에 "구성 미정".
- 배 강수 270mm: "생육단계 미정".
- 감자 강수: ETc 상대값이라 절대값(mm) 환산 불가.
- 배 개화기 저온 -1.7~-2.5℃(나주 배시험장 국내 실측): 값 자체는 신뢰도가 높으나
  crop_growth_stage에 개화기(flowering) 단계가 없어 지금 넣으면 전기간(NULL)에 걸려
  겨울에도 상시 위험으로 판정된다. 단계 시드 추가가 선행 조건 → [확인 필요].
- 상추 최적 주간 22~26℃(문헌 30번): 식물공장(plant factory) 조건이라 노지 기준과 다르다.
- EC 사과 0.8~1.5 dS/m: LoopReport Registry에서 "신뢰도 낮음/일부"로 표시돼 잠정치로만.

**단위**: 강수는 0011에서 rainfall_monthly(mm/월)로 분리했다. 일 단위 과습 임계
(문헌 "일 30~50mm")는 rainfall_daily로 새로 넣는다 — 단기 탭 예보(일누적)와 단위가 맞다.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOOP = "LoopReport.md (자율 연구 루프 Iter1~4, 논문 39편 중 28편 검증)"
DBPIA = "기온강수량-문헌정리.md (DBpia 39편)"


def upgrade() -> None:
    op.execute(
        f"""
        -- 1) 기존 행에 근거·신뢰도 소급 기입. 0004 시드는 농사로 작물별 안내책자 기반이다.
        UPDATE crop_growth_guide
           SET source_ref = '농촌진흥청 농사로 작물별 안내책자(0004 시드)',
               confidence = 'domestic_measured'
         WHERE source_ref IS NULL;

        -- 2) 문헌에서 확정된 값 추가/갱신.

        -- 사과 토양반응 pH 6.0 전후(농사로 재배환경: "사과나무 생육에 적절한 토양반응은
        -- pH 6.0 정도"). LoopReport도 6.0~6.5로 정합.
        INSERT INTO crop_growth_guide
            (crop_id, growth_stage, indicator, optimal_min, optimal_max,
             allowed_min, allowed_max, weight, source_ref, confidence)
        VALUES
            (1, NULL, 'ph', 6.0, 6.5, 5.5, 7.0, 1.5,
             '농사로 사과 재배환경 + {LOOP}', 'domestic_measured'),
            -- 배 pH 5.8~7.0 (LoopReport Registry filled)
            (2, NULL, 'ph', 5.8, 7.0, 5.5, 7.5, 1.5,
             '{LOOP}', 'foreign_literature')
        ON CONFLICT (crop_id, growth_stage, indicator) DO UPDATE
            SET optimal_min = EXCLUDED.optimal_min,
                optimal_max = EXCLUDED.optimal_max,
                allowed_min = EXCLUDED.allowed_min,
                allowed_max = EXCLUDED.allowed_max,
                weight = EXCLUDED.weight,
                source_ref = EXCLUDED.source_ref,
                confidence = EXCLUDED.confidence;

        -- 사과 고온 한계 31℃로 갱신(기존 허용상한 30 → 문헌값 31).
        UPDATE crop_growth_guide
           SET allowed_max = 31,
               source_ref = '{LOOP} — 사과 고온 임계 31℃',
               confidence = 'foreign_literature'
         WHERE crop_id = 1 AND growth_stage = 'fruit_growth' AND indicator = 'temp_day';

        -- 감자 괴경비대기 야간 고온 28℃ 초과 시 괴경 형성 중단(Zhang 2024).
        UPDATE crop_growth_guide
           SET allowed_max = 28,
               source_ref = '{LOOP} — 감자 야간 28℃ 괴경형성 중단(Zhang 2024)',
               confidence = 'foreign_literature'
         WHERE crop_id = 4 AND growth_stage = 'tuber' AND indicator = 'temp_night_min';

        -- 감자 잎 냉해 -3℃(Stegner 2019). 초기 생육 단계의 하한 경보로 사용.
        UPDATE crop_growth_guide
           SET allowed_min = -3,
               source_ref = '{LOOP} — 감자 잎 냉해 -3℃(Stegner 2019)',
               confidence = 'foreign_literature'
         WHERE crop_id = 4 AND growth_stage = 'early' AND indicator = 'temp_day';

        -- 오이·상추 고온 30℃ 근거 기입(값은 기존과 동일 — 문헌이 뒷받침).
        UPDATE crop_growth_guide
           SET source_ref = '{LOOP} — 오이/상추 고온 30℃',
               confidence = 'foreign_literature'
         WHERE crop_id IN (3, 5) AND growth_stage IS NULL AND indicator = 'temp_day';

        -- 3) 일 강수 과습 임계(문헌: 일 30~50mm에서 토양 산소부족 → 생육 저해).
        --    단기 탭 예보(일누적)와 단위가 맞는 신규 지표. 5작물 공통이라 전기간(NULL)에 둔다.
        --    적정 하한을 두지 않는다 — "비가 안 온 날"은 과습 위험이 아니다(단위 혼동 재발 방지).
        INSERT INTO crop_growth_guide
            (crop_id, growth_stage, indicator, optimal_min, optimal_max,
             allowed_min, allowed_max, weight, source_ref, confidence)
        SELECT id, NULL, 'rainfall_daily', 0, 30, NULL, 50, 1.5,
               '{LOOP} — 일 30~50mm 과습 임계(Zhang 2025 리뷰)', 'foreign_literature'
          FROM crop
        ON CONFLICT (crop_id, growth_stage, indicator) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM crop_growth_guide WHERE indicator = 'rainfall_daily';
        DELETE FROM crop_growth_guide
         WHERE indicator = 'ph' AND crop_id IN (1, 2) AND growth_stage IS NULL;

        UPDATE crop_growth_guide SET allowed_max = 30
         WHERE crop_id = 1 AND growth_stage = 'fruit_growth' AND indicator = 'temp_day';
        UPDATE crop_growth_guide SET allowed_max = NULL
         WHERE crop_id = 4 AND growth_stage = 'tuber' AND indicator = 'temp_night_min';
        UPDATE crop_growth_guide SET allowed_min = 5
         WHERE crop_id = 4 AND growth_stage = 'early' AND indicator = 'temp_day';

        UPDATE crop_growth_guide SET source_ref = NULL, confidence = NULL;
        """
    )
