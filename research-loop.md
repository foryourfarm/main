---
description: 논문 도메인 지식 수집 루프를 실행한다. scout(한국어는 WebSearch, 영어는 Aira MCP로 분리 검색) → extractor(들) → registry-keeper 순으로 서브에이전트를 호출하며, registry.md 기준 정지 조건에 도달하거나 최대 반복 횟수에 닿거나 사용자가 "멈춰"라고 말할 때까지 반복한다. git은 일절 사용하지 않는다.
argument-hint: [max_iterations] [focus_keyword(선택)]
---

# 오케스트레이터 지침

당신은 이 루프의 오케스트레이터입니다. **당신 자신의 컨텍스트를 작게 유지하는 것이
최우선 규칙**입니다. 아래 원칙을 반드시 지키십시오.

## 절대 규칙

1. **`knowledge-base/papers/**/*.md`(개별 논문 정리본)를 직접 Read하지 마시오.**
   그 파일들은 extractor가 쓰고, 필요한 사람이 나중에 직접 열어보는 용도입니다.
   당신은 파일 경로와 registry.md의 요약 행만으로 판단합니다.
2. 매 루프 시작 시 `knowledge-base/registry.md`와 `knowledge-base/keyword-queue.md`만
   Read하십시오. 다른 파일은 필요할 때만(예: search-log.md 중복 확인) 최소한으로 엽니다.
3. 무거운 작업(검색, 원문 읽기, 8단계 정리, registry 갱신)은 전부 Task 도구로
   서브에이전트(`scout`, `extractor`, `registry-keeper`)를 호출해서 위임하십시오.
   당신이 직접 웹 검색을 하거나 논문 원문을 fetch하지 마십시오.
4. 서브에이전트 호출 시 프롬프트에는 **필요한 최소 정보만** 넣으십시오(예: registry.md
   전체가 아니라 관련된 몇 줄만 발췌해서 전달).
5. **git을 일절 사용하지 마십시오.** 이 루프는 파일 시스템에 읽고 쓰는 것으로 끝입니다.
   `git add`, `git commit`, `git push`, 브랜치 생성 등 어떤 버전관리 명령도 실행하지
   마십시오(직접 실행하지도, 서브에이전트에게 시키지도 마십시오). 커밋 시점과 방식은
   전적으로 사람이 결정합니다.
6. **사용자가 "멈춰"라고 말하면 그 즉시 루프를 중단하십시오.** 자세한 절차는 아래
   "중단 처리" 섹션을 따르십시오. 반복 횟수가 남아있어도, 지금 처리 중인 사이클이
   끝나지 않았어도 예외 없이 중단합니다.

## 중단 처리 ("멈춰")

이 루프는 여러 번의 Task 호출로 구성되므로, 사용자가 "멈춰"라고 말할 수 있는 시점은
크게 두 가지입니다.

- **서브에이전트 호출 사이(턴 경계)**: 매 서브에이전트(scout/extractor/registry-keeper)
  호출 직후, 다음 단계로 넘어가기 전에 반드시 대화에 사용자가 "멈춰"(또는 이를 포함한
  메시지)를 보냈는지 확인하십시오. 확인되면:
  1. 지금 막 반환받은 결과까지는 정상 처리하되(예: registry-keeper가 이미 응답한 delta는
     반영), 다음 서브에이전트 호출이나 다음 반복(iteration)은 **시작하지 않습니다**.
  2. registry.md가 이번 사이클 중간에 갱신되지 않았다면, 지금까지 모인 deltas만이라도
     registry-keeper를 한 번 호출해 반영할지 판단하십시오(이미 두 번 이상 사이클을 돌았고
     반영 안 된 delta가 있다면 반영, 없으면 그냥 종료).
  3. 사용자에게 "사용자 요청으로 루프를 중단했습니다"라는 문구와 함께, 그 시점까지의
     진행 요약(처리된 논문 수, 신규 filled, 남은 gap)을 짧게 보고하고 종료합니다.
- **서브에이전트 실행 도중(Claude Code CLI 인터럽트)**: 사용자가 Claude Code 인터페이스에서
  직접 실행을 중단시킨 경우(예: ESC 또는 인터럽트), 이는 이 커맨드의 지침과 무관하게
  즉시 적용됩니다 — 이 경우 별도 처리를 시도하지 말고 중단된 상태 그대로 두십시오.

이 확인은 매 반복(iteration)마다, 그리고 이상적으로는 각 Task 호출 직후마다 반복해서
수행하십시오. "한 번 확인했으니 끝까지 안 봐도 된다"고 가정하지 마십시오.

## 인자

- `$1` (max_iterations): 최대 루프 반복 횟수. 생략 시 15.
- `$2` (focus_keyword): 특정 gap에 집중하고 싶을 때만 지정. 생략 시 큐 최상단을 사용.

## 루프 절차

```
iteration = 0
Read knowledge-base/registry.md (요약만 파악)
Read knowledge-base/keyword-queue.md

while iteration < max_iterations:
    iteration += 1

    if 사용자의_최근_메시지에_"멈춰"가_있음:
        break  # "중단 처리" 섹션 절차대로 마무리 보고 후 종료

    # 1. 이번 사이클의 타겟 키워드 결정
    if focus_keyword가 주어졌고 iteration == 1:
        target = focus_keyword
    else:
        target = keyword-queue.md 최상단 항목 (없으면 stop: "큐가 비었습니다")

    # 2. scout 호출 (scout은 한국어는 WebSearch로, 영어는 Aira로 나눠 검색함)
    Task(subagent="scout", prompt=f"""
        gap_keyword: {target}
        target_context: <registry.md에서 이 키워드와 연관된 행 1~2줄 발췌해서 전달>
        already_seen: <search-log.md에서 관련 부분만 발췌, 없으면 "없음">
    """)
    → scout_result 받음 (candidates 목록, YAML)

    if 사용자의_최근_메시지에_"멈춰"가_있음:
        break

    if scout_result.no_result == true:
        keyword-queue.md에서 target 제거, search-log.md에 "결과없음"으로 기록
        continue  # 이번 사이클은 extractor 호출 없이 다음 반복으로

    # 3. 채택할 후보 선정
    scout_result.candidates 중 relevance_note를 보고 관련성 높은 순으로
    최대 3편을 채택한다(전부 억지로 채택하지 않는다 — 관련성 낮으면 스킵).

    # 4. 채택된 논문마다 extractor 호출 (순차 또는 병렬)
    for candidate in 채택된_후보들:
        if 사용자의_최근_메시지에_"멈춰"가_있음:
            break  # 이미 시작된 extractor 호출은 완료시키되 다음 후보는 스킵

        Task(subagent="extractor", prompt=f"""
            paper_metadata: {candidate}
            registry_snapshot: <registry.md에서 이 crop/indicator 관련 행만 발췌>
            target_schema_fields: <DB.md 기준으로 이 논문이 채울 만한 필드 힌트>
        """)
        → delta 받음, deltas 리스트에 추가

    # 5. registry-keeper 호출 (이번 사이클의 모든 delta를 한 번에 전달)
    Task(subagent="registry-keeper", prompt=f"""
        deltas: {deltas}
        scout_meta:
            searched_queries: {scout_result.searched_queries}
            no_result: {scout_result.no_result}
            korean_coverage_weak: {scout_result.korean_coverage_weak}
    """)
    → keeper_result 받음

    # 6. 정지 조건 확인
    if 사용자의_최근_메시지에_"멈춰"가_있음:
        break
    if keeper_result.stop_recommended == true:
        사용자에게 보고: keeper_result.stop_reason, 처리된 논문 수, 남은 gap 요약
        break

    # 7. 진행 상황 짧게 보고(전체 registry 덤프 금지 — 요약만)
    print(f"[{iteration}/{max_iterations}] +{keeper_result.papers_added_this_cycle}편 처리, "
          f"신규 filled: {keeper_result.newly_filled}, 남은 우선순위 gap: "
          f"{keeper_result.still_missing_high_priority}")

# 루프 종료 후 최종 요약
Read knowledge-base/registry.md 표1·표2의 status 분포만 집계해서 사람에게 보고.
표 4(알려진 구조적 이슈)가 있으면 반드시 함께 보고 — 이건 팀이 결정해야 할 사항이므로
자동으로 넘기지 않는다.
```

## 병렬화에 대한 참고

한 사이클에서 채택된 논문이 여러 편이면, extractor 호출은 서로 독립적이므로 병렬로
Task를 여러 개 띄워도 됩니다(서로 다른 논문을 읽는 작업이라 상태 충돌이 없음). 다만
registry-keeper는 그 사이클의 모든 delta가 모인 뒤 **한 번만** 호출하십시오 — extractor
결과마다 매번 호출하면 registry.md에 대한 쓰기 경쟁이 생기고 갱신 히스토리가 지저분해집니다.

## 사람에게 보고할 때

- registry.md 전체 내용을 채팅에 그대로 붙여넣지 마십시오. 상태 분포 요약(예: "crop_growth_guide
  42개 셀 중 filled 18 / partial 9 / missing 15")과 표 4(구조적 이슈)만 보고합니다.
- 구조적 이슈(예: "질소 지표가 indicator 목록에 없음")는 자동으로 해결하지 말고 반드시
  사람의 결정을 요청하십시오.
