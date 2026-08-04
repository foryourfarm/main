# vLLM 전환 — 방법론과 실행 순서

> 갱신: 2026-08-04. 발단은 **"평가 때 6명이 동시에 쓴다"**는 요구다.
> 지금 Ollama 구성은 그 부하에서 6번째 사용자가 **첫 토큰까지 40초**를 기다린다(아래 §1 실측).
>
> 관련 문서: [`llm-integration.md`](./llm-integration.md)(LLM 계약·폴백 규칙),
> [`infra/ollama-vm/README.md`](../infra/ollama-vm/README.md)(VM 구성).

---

## 1. 왜 바꾸는가 — 실측 기준선

로컬(RTX 5070 8GB, Ollama 0.31.1, `exaone3.5:7.8b`)에서 **실제 RAG 경로**로 쟀다.
검색은 미리 끝내고 생성만 동시에 던져 임베딩 경합을 변수에서 제거했다.

    단독 1건        첫토큰  3.6s | 총  9.7s | 447자
    동시 6건        첫토큰  4.5s | 총 10.9s
                    첫토큰 12.3s | 총 17.5s
                    첫토큰 19.2s | 총 24.4s
                    첫토큰 25.7s | 총 31.9s
                    첫토큰 33.0s | 총 38.8s
                    첫토큰 40.2s | 총 47.0s
                    >> 6건 전체 완료 47.0s

**첫토큰이 약 7초씩 계단식으로 늘어난다** — 병렬 처리가 아니라 거의 순차 처리다.
전체 47초 ≈ 단독 9.7초 × 5배. 원인은 `OLLAMA_NUM_PARALLEL`이 설정되지 않은 것이고
(`infra/ollama-vm/startup.sh`의 `override.conf`에 `OLLAMA_HOST`만 있다) VM도 같은 상태다.

**UX 판정**: 6번째 사용자는 질문 후 40초간 빈 화면을 본다. 프론트에 대기 순번 표시가 없어
"고장났다"고 판단할 시간이다. **첫토큰 이후는 6초라 빠르다 — 문제는 첫토큰까지다.**

> **대안을 먼저 검토했다**: `OLLAMA_NUM_PARALLEL=4` 한 줄로 완화될 가능성이 있었다
> (양자화 모델이 5.7GB뿐이라 L4 24GB에 KV캐시 여유가 크다). 팀 결정은 vLLM 전환이며
> (2026-08-04), 근거는 continuous batching이 계단식 대기를 구조적으로 없앤다는 것이다.
> 그 한 줄 시도는 **롤백 경로로 남겨둔다**(§6).

---

## 2. 확정된 사실 (추측 금지 — §3-4)

| 항목 | 확인 결과 | 출처 |
|---|---|---|
| vLLM의 EXAONE 지원 | **`ExaoneForCausalLM`** 아키텍처로 지원 | vLLM `docs/models/supported_models.md` |
| EXAONE 3.5 AWQ 양자화판 | **존재** — `LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-AWQ`, 4-bit W4A16g128 | HF 모델 카드 |
| 공식 기동 명령 | `vllm serve "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-AWQ"` | 같은 모델 카드 |
| 라이선스 | **EXAONE AI Model License Agreement 1.1 - NC** (비상업) | 같은 모델 카드 |

**⚠️ 아직 확정되지 않은 것**: 지원 목록의 `ExaoneForCausalLM` 예시는 **EXAONE-3.0**이다.
3.5가 같은 아키텍처를 쓰는 것은 HF config 기준이지만, **특정 vLLM 버전에서 3.5 AWQ가 실제로
로드되는지는 VM에서 띄워봐야 확정된다.** §5의 첫 단계가 이것이고, 실패하면 거기서 멈춘다.

**⚠️ 라이선스가 NC(비상업)다.** 지금 Ollama도 같은 모델을 쓰므로 vLLM이 새로 만드는 위험은
아니지만(선재 조건), 해커톤 밖으로 나가면 확인이 필요하다. **[확인 필요]**

---

## 3. VRAM — **반드시 AWQ로 가야 한다**

EXAONE 3.5 7.8B 구조(HF config): 32 layer · 8 KV head(GQA) · head_dim 128.
KV캐시 = `2(K,V) × 32 × 8 × 128 × 2B` = **토큰당 128 KiB**.

    ctx 8192 × 슬롯 1 = 1.1 GB
    ctx 8192 × 슬롯 4 = 4.3 GB
    ctx 8192 × 슬롯 6 = 6.4 GB
    ctx 8192 × 슬롯 8 = 8.6 GB

L4 = 24GB 기준 총량:

    구성    가중치  + KV(8192×6)  + bge-m3   = 합계    여유
    bf16     15.6     6.4          0.7        22.7    1.3GB   ← 위험
    AWQ       4.5     6.4          0.7        11.6   12.4GB   ← OK

**bf16으로 띄우면 여유가 1.3GB뿐이라 OOM 위험이 크다.** AWQ면 12.4GB가 남아 슬롯을 더 늘릴
여지까지 있다.

**참고 — Ollama가 이미 양자화판이다.** `ollama list`의 `exaone3.5:7.8b`는 4.8GB 파일이고
실측 VRAM 5.7GB다(`/api/ps`). 즉 "vLLM으로 바꾸면 더 무거워진다"가 bf16 기준으로는 사실이며,
AWQ를 써야 비슷한 수준을 유지한다.

**⚠️ AWQ의 트레이드오프**: L4는 Ada 세대라 W4A16을 잘 돌리지만, AWQ는 bf16보다 **단독 응답이
약간 느릴 수 있다.** 목표가 동시 6명 처리량이므로 방향은 맞지만, §7의 검증에서 단독 지연이
크게 나빠지지 않았는지 함께 본다.

---

## 4. 구조적 장애물 — 임베딩이 같은 주소를 쓴다

`embedding_client.py`가 **`settings.llm_base_url`을 그대로 쓴다**:

```python
self.base_url = base_url or settings.llm_base_url   # LLM과 같은 주소
```

즉 지금은 한 주소(`:11434`)로 생성·임베딩을 둘 다 부른다. **vLLM은 한 프로세스에 한 모델**이라
이 구조가 그대로 갈 수 없다.

### 선택지와 판단

| 방안 | 구성 | 판단 |
|---|---|---|
| **A. vLLM(생성) + Ollama(임베딩)** | vLLM `:8000` + Ollama `:11434` | **채택** |
| B. vLLM 단독(임베딩도 vLLM) | vLLM 인스턴스 2개 | ❌ 프로세스 수는 같은데 **재임베딩 위험만 추가** |
| C. 유지 | — | ❌ 동시성 미해결 |

**A를 택하는 결정적 이유는 재임베딩 회피다.** `embedding_client.py` docstring이 못박고 있다 —
*"`scripts/embed_corpus.py`가 적재 때 쓴 모델과 반드시 같아야 코사인 유사도가 의미를 가진다."*
Ollama bge-m3를 유지하면 **936청크를 다시 만들 필요가 없다.** vLLM의 bge-m3는 풀링·정규화가
다를 수 있어 검증 없이는 같은 벡터 공간이라고 단정할 수 없다.

---

## 5. 실행 순서 — 위험도 순으로 쪼갠다

### 1단계 — 임베딩 주소 분리 (위험 0, 서버 불필요)

`embedding_base_url` 설정을 새로 만들고 **기본값을 `llm_base_url`과 같게** 둔다.
→ **동작이 전혀 바뀌지 않는다.** vLLM 없이 머지 가능하고, 나중에 주소만 바꾸면 전환된다.
`test_env_example_matches_settings.py`가 env 이름 드리프트를 잡아준다(§17).

### 2단계 — `VllmClient` 구현 + 캔드 테스트 (위험 0, 서버 불필요)

`LlmClient` Protocol이 이미 있어 `generate`/`generate_stream` 두 개만 맞추면 된다.
Ollama와 다른 점:

| | Ollama | vLLM(OpenAI 호환) |
|---|---|---|
| 경로 | `/api/generate` | `/v1/chat/completions` |
| 입력 | `prompt` 문자열 | `messages` 배열 |
| 스트림 | JSON 줄마다 `response` | SSE `data: {...}` + `data: [DONE]` |
| 컨텍스트 창 | `options.num_ctx`(요청마다) | **`--max-model-len`(서버 기동 플래그)** |

**`num_ctx`를 요청으로 못 준다**는 점이 중요하다 — PR #97에서 고친 `llm_num_ctx=8192`가
vLLM에서는 **서버 기동 시 고정**된다. 클라이언트는 그 값을 검증만 할 수 있다.

검증은 실서버 없이 한다 — OpenAI 스트리밍 응답을 캔드 데이터로 넣어 파싱 테스트.
(현재 `OllamaClient`에는 그런 테스트가 없다. 새로 만드는 쪽에는 붙인다.)

### 3단계 — VM에 vLLM 병행 기동 (**진짜 위험 구간**)

`startup.sh`에 vLLM을 추가하고 **Ollama는 임베딩 전용으로 남긴다.**

확인 순서(앞이 실패하면 멈춘다):

1. **`ExaoneForCausalLM`로 3.5 AWQ가 실제 로드되는가** (§2의 미확정 항목)
2. `--max-model-len 8192` — PR #97의 `num_ctx`에 대응
3. `--gpu-memory-utilization` — Ollama 몫(bge-m3 0.7GB + 여유)을 남긴다. vLLM 기본은 0.9로
   **거의 전부 선점**하므로 반드시 낮춘다
4. `--max-num-seqs` — 동시 슬롯. §3 표로 6~8이 여유 범위
5. 워밍업 curl + `llm_timeout_s=90`이 vLLM 콜드로드에 충분한지 재확인
   (Ollama 콜드가 실측 67초였고 vLLM은 더 느릴 수 있다)

### 4단계 — 환경변수로 전환

`LLM_BASE_URL`을 `:8000`으로 바꾸면 전환, 되돌리면 롤백이다.
**재배포 없이 `gcloud run services update --update-env-vars`로 가능하다.**

> ⚠️ `--set-env-vars`를 쓰면 기존 환경변수 19개가 전부 삭제된다(README §⑤ 경고).
> 반드시 `--update-env-vars`를 쓴다.

---

## 6. 롤백

| 상황 | 조치 |
|---|---|
| vLLM이 로드 실패 | `LLM_BASE_URL`을 `:11434`로 되돌린다(Ollama는 계속 떠 있다) |
| 동시성이 기대만큼 안 나옴 | 같은 방법으로 되돌린 뒤 `OLLAMA_NUM_PARALLEL=4`를 시도(§1의 미시도 대안) |
| VRAM 부족 | `--max-num-seqs`·`--max-model-len`을 낮춘다. 그래도 안 되면 롤백 |

**Ollama를 끄지 않는 것이 롤백 전략의 핵심이다.** 임베딩 때문에 어차피 떠 있어야 하므로
생성 경로만 주소로 갈아타면 된다.

---

## 7. 검증 기준 — §1의 숫자와 같은 방법으로 비교

    항목                     Ollama(기준선)   vLLM 목표
    단독 첫토큰                3.6s           크게 나빠지지 않을 것(AWQ 트레이드오프)
    동시 6건 첫토클 최대       40.2s          **평탄해야 한다** — 계단식이면 실패
    동시 6건 전체 완료         47.0s          단축

**계단식(약 7초씩 증가)이 사라지는지가 성공 판정 기준이다.** continuous batching이 먹히면
첫토큰이 사용자 수에 비례해 늘지 않는다. 그게 안 나오면 전환 이득이 없으니 §6으로 되돌린다.

측정 스크립트는 §1과 동일한 방식(검색 미리 수행 + 생성만 동시 6건)으로 재사용한다.

---

## 8. 미해결 / 확인 필요

- **[확인 필요] EXAONE 라이선스 NC(비상업)** — 해커톤 범위 밖 사용 시 재검토.
- **[확인 필요] vLLM 버전별 3.5 AWQ 로드 가능 여부** — §5-3의 첫 단계에서 확정.
- **동시성 병목을 프로덕션에서 측정한 적이 없다.** §1은 로컬(8GB) 실측이고 L4(24GB)와
  절대값이 다르다. 경향(계단식 대기)은 구성 문제라 재현될 것으로 보지만, 전환 후 §7을
  **VM에서** 다시 재는 것이 원칙이다.
- `OllamaClient`에 파싱 테스트가 없다 — 2단계에서 `VllmClient`에는 붙이지만, 기존 쪽은
  그대로 남는다(별건).
