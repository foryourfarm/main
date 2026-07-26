---
description: 도메인 지식 수집 루프를 **자동 순환**으로 실행한다. problem-extractor → targeted-searcher → conflict-checker → extractor → registry-keeper 순서로 반복하며, 사용자 개입 없이 계속 돈다. 정지 조건(registry 커버리지 완성, 최대 반복, "멈춰" 명령)에 도달하면 종료.
argument-hint: [max_iterations] [--dry-run]
---

# 오케스트레이터 지침

당신은 자동 순환 루프의 오케스트레이터입니다. **사용자 개입 없이 계속 도는 것**이 목표입니다.

## 절대 규칙

1. **컨텍스트 최소화**: `knowledge-base/registry.md`와 `keyword-queue.md`만 읽으세요. 논문 정리본 전체를 읽지 마세요.
2. **서브에이전트 호출 위임**: 무거운 작업(문제 식별, 검색, 원문 읽기, 검증, 갱신)은 전부 서브에이전트에게 위임.
3. **자동 순환**: 정지 조건까지 계속 반복. 사용자가 "멈춰"라고 말할 때까지 멈추지 않음.
4. **Git 금지**: 이 루프는 파일 읽기/쓰기만 합니다. git 명령 절대 금지.
5. **사용자 개입 최소화**: 진행 상황은 간단히만 보고(전체 registry 덤프 금지). 매우 문제가 생기면 중단하고 보고.

## 인자

- `$1` (max_iterations): 최대 루프 반복 횟수. 생략 시 20.
- `$2` (--dry-run): 실제 파일 쓰기 전에 계획만 보여줌(테스트용).

## 루프 절차

```
iteration = 0
Read knowledge-base/registry.md (상태만 파악)
Read knowledge-base/keyword-queue.md (문제 목록 확인)

while iteration < max_iterations:
    iteration += 1

    # 사용자 중단 확인 (매 반복마다)
    if 사용자_최근_메시지에_"멈춰"가_있음:
        break

    # 1. problem-extractor 호출
    #    기존 정리본들(Apple-정리.md, Pear-정리.md 등)을 읽어서
    #    "다음에 무엇을 찾아야 하는가"를 식별
    Task(subagent="problem-extractor", prompt=f"""
        knowledge_base_path: knowledge-base/
        registry_path: knowledge-base/registry.md
        
        기존 정리본들의 "보완" 섹션과 "꼭 필요한 정보"를 추출해서
        우선순위별 문제 목록을 생성하세요.
    """)
    → problem_result 받음 (problem_list, priority 정렬)

    if 사용자_최근_메시지에_"멈춰"가_있음:
        break

    # problem_result가 비어있으면(더 이상 미충족 항목 없음) 루프 종료
    if problem_result.total_problems == 0:
        사용자에게 보고: "모든 문제가 해결되었습니다."
        break

    # 2. 우선순위 상위 문제들에 대해 targeted-searcher 호출 (병렬)
    #    한 번에 1~2개 문제만(너무 많으면 컨텍스트 폭증)
    top_problems = problem_result.problem_list[:2]  # 상위 2개만
    
    search_results = []
    for problem in top_problems:
        if 사용자_최근_메시지에_"멈춰"가_있음:
            break
        
        Task(subagent="targeted-searcher", prompt=f"""
            target_problem: {problem.problem}
            suggested_queries: {problem.suggested_queries}
            search_strategy: {problem.search_strategy}
            already_seen: <registry.md / search-log.md에서 관련 부분만 발췌>
        """)
        → search_result 받음 (candidates 5~10편)
        search_results.append(search_result)

    if 사용자_최근_메시지에_"멈춰"가_있음:
        break

    # 3. conflict-checker 호출 (검증)
    #    찾은 논문들이 기존과 모순되지 않는지 확인
    all_candidates = [c for s in search_results for c in s.candidates]
    
    if len(all_candidates) > 0:
        Task(subagent="conflict-checker", prompt=f"""
            candidates: {all_candidates}
            existing_papers_summary: <Apple-정리.md 등에서 핵심 수치 추출해서 전달>
            potential_conflicts: <각 후보가 이미 메모한 충돌 신호>
        """)
        → validation_result 받음 (approved, caution, rejected)
        
        approved_candidates = [c for c in validation_result.validation_results if c.status == "approve"]
        caution_candidates = [c for c in validation_result.validation_results if c.status == "caution"]
    else:
        approved_candidates = []
        caution_candidates = []

    if 사용자_최근_메시지에_"멈춰"가_있음:
        break

    # 4. extractor 호출 (원문 읽기)
    #    approved + caution(주의사항 포함) 논문들을 원문 읽고 8단계 정리
    extraction_targets = approved_candidates + caution_candidates  # 둘 다 진행
    deltas = []
    
    for candidate in extraction_targets:
        if 사용자_최근_메시지에_"멈춰"가_있음:
            break
        
        caution_note = ""
        if candidate in caution_candidates:
            caution_note = f"⚠️ {candidate.conflict_notes} → {candidate.extractor_instruction}"
        
        Task(subagent="extractor", prompt=f"""
            paper_metadata: {candidate}
            registry_snapshot: <registry.md에서 관련 행만 발췌>
            target_schema_fields: <DB.md 기준 힌트>
            {f"caution_note: {caution_note}" if caution_note else ""}
        """)
        → delta 받음
        deltas.append(delta)

    if 사용자_최근_메시지에_"멈춰"가_있음:
        break

    # 5. registry-keeper 호출 (상태 갱신)
    if len(deltas) > 0:
        Task(subagent="registry-keeper", prompt=f"""
            deltas: {deltas}
            scout_meta:
                searched_queries: {모든_검색_쿼리들}
                no_result: false (targeted-searcher는 항상 뭔가 찾으니까)
                korean_coverage_weak: <필요시>
        """)
        → keeper_result 받음

    # 6. 정지 조건 확인
    Read knowledge-base/registry.md (최신 상태)
    if registry.md의_커버리지가_충분히_높으면:  # 예: 5작물 × 핵심지표 90% 이상 filled
        사용자에게 보고: "목표 커버리지 달성. 루프 종료."
        break
    
    # 7. 진행 상황 간단히 보고
    print(f"[반복 {iteration}/{max_iterations}]")
    print(f"  발굴: {len(all_candidates)}편")
    print(f"  승인: {len(approved_candidates)}편")
    print(f"  처리됨: {len(deltas)}편")
    if keeper_result:
        print(f"  신규 filled: {keeper_result.newly_filled}")
    print()

# 루프 종료 후 최종 요약
Read knowledge-base/registry.md
사용자에게 보고:
  - 총 반복 횟수
  - 최종 커버리지 분포 (missing / partial / filled)
  - 남은 주요 gap (상위 5개)
  - 알려진 구조적 이슈 (표 4)
```

## 병렬화 참고

- **targeted-searcher**: 여러 문제에 대해 동시에 호출 가능 (독립적이므로)
- **extractor**: 여러 논문에 대해 동시에 호출 가능
- **registry-keeper**: 한 사이클의 모든 delta가 모인 후 **한 번만** 호출 (쓰기 경합 방지)

## 사용자 중단 ("멈춰")

이 루프는 사용자가 대화 중 "멈춰"라고 말할 수 있는 여러 지점이 있습니다:
- **서브에이전트 호출 사이**: 즉시 감지하고 그 지점에서 중단
- **서브에이전트 실행 도중**: Claude Code가 인터럽트하면 즉시 중단됨

매 반복 시작 전과 각 Task 호출 후에 사용자 메시지를 확인하세요.

## 에러 처리

- **targeted-searcher가 no_result 반환**: 그 문제는 스킵하고 다음으로 진행
- **extractor가 blocked (원문 미접근)**: 그 논문은 스킵, 다음 논문 진행
- **registry-keeper 갱신 실패**: 경고하고 다음 반복으로 진행 (중단하지 않음)

어떤 에러도 루프 전체를 중단시키지 않되, 발생한 에러는 매 반복마다 사용자에게 보고합니다.

# 하지 말아야 할 것

- `knowledge-base/papers/**/*.md` 정리본 전체를 읽지 마세요.
- 단순히 진행 상황을 위해 git을 사용하지 마세요.
- 매 반복마다 registry.md 전체를 사용자에게 출력하지 마세요 (요약만).
