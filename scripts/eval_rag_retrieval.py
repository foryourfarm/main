"""RAG 검색 품질 측정: 청크 크기 · top-k · 임베딩 텍스트 구성 스윕.

`chunk_corpus.TARGET_CHARS/MAX_CHARS`와 `settings.rag_top_k`를 **감으로 정하지 않기 위한**
측정 도구다. 청킹 설정별로 코퍼스를 메모리에서 다시 자르고 bge-m3로 임베딩해, 질문마다
정답 근거가 top-k 안에 들어오는 비율(hit@k)을 센다.

정답 정의: 질문에 실제로 답하는 구절만 걸리는 필수 패턴 묶음(gold). 청킹 설정이 바뀌면
청크 경계가 바뀌므로 "청크 id"가 아니라 **내용**으로 정답을 판정한다. 정답 청크가 흔한
질문(> MAX_GOLD)은 어떤 설정이든 맞아 변별력이 없어 스윕에서 뺀다.

**한계**: 문항 19개(희소성 필터 통과분)라 1문항이 5%p다. 설정 간 1문항 차이는 노이즈로
보고, 여러 설정에서 같은 방향이 반복될 때만 신호로 읽는다.

사용법 (Ollama 실행 + `ollama pull bge-m3` 필요):
    backend/.venv/Scripts/python.exe scripts/eval_rag_retrieval.py
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import chunk_corpus as cc  # noqa: E402

DATA = REPO / "data"
# 임베딩 캐시(내용 해시 -> 벡터). 설정 스윕은 같은 청크를 여러 번 만나므로 캐시가 없으면
# 같은 텍스트를 수천 번 다시 임베딩한다. 재현 실행도 이 파일이 있으면 몇 초로 끝난다.
CACHE = REPO / "data" / "_rag_eval_emb_cache.jsonl"
OLLAMA = "http://localhost:11434"
MODEL = "bge-m3"

# (작물, 질문, [필수 패턴들]) — 모든 패턴이 한 청크 안에 있으면 그 청크를 정답으로 본다.
QUERIES = [
    ("apple", "사과나무에 질소 비료를 얼마나 줘야 하나요?", ["시비량", "질소", "kg/10a|㎏/10a"]),
    ("apple", "사과밭 지하수위가 높으면 나무가 어떻게 되나요?", ["지하수위", "고사|생육"]),
    ("apple", "사과 저장할 때 온도는 몇 도로 맞춰야 하나요?", ["저장", "℃", "저장고|예냉|CA"]),
    ("apple", "사과원 토양 유기물이 부족한데 어떻게 하나요?", ["유기물", "시용|퇴비", "kg|톤|%"]),
    ("apple", "사과 겹무늬썩음병은 어떻게 방제하나요?", ["겹무늬썩음병", "방제|약제|살포"]),
    ("apple", "사과나무 전정은 언제 어떻게 하나요?", ["전정", "시기", "겨울|휴면|월"]),
    ("apple", "사과원 흙이 산성인데 석회를 얼마나 넣나요?", ["석회", "pH|산성", "kg|시용량|사용량"]),
    ("pear", "배 인공수분은 언제 해야 하나요?", ["인공수분", "개화|만개", "꽃가루|화분"]),
    ("pear", "배 봉지는 언제 씌우나요?", ["봉지", "씌우", "시기|월|낙화"]),
    ("pear", "배 검은별무늬병 방제 방법이 궁금합니다", ["검은별무늬병", "방제|약제"]),
    ("pear", "배 열매솎기는 어느 정도로 하나요?", ["적과", "엽수|과실수|간격"]),
    ("pear", "배 수확 적기는 어떻게 판단하나요?", ["수확", "적기|만개\\s?후"]),
    ("pear", "배나무 시비량은 얼마인가요?", ["시비량", "질소|인산|칼리", "kg/10a|㎏/10a"]),
    ("pear", "배 저온저장고 온도는 몇 도로 맞추나요?", ["저장", "℃", "저장고|예건"]),
    ("pear", "배 밑거름은 언제 주나요?", ["밑거름", "낙엽기|휴면기|겨울"]),
    ("potato", "씨감자를 자를 때 소독은 어떻게 하나요?", ["절단", "소독|큐어링|아물"]),
    ("potato", "감자 역병 증상이 뭔가요?", ["역병", "병징|증상|반점"]),
    ("potato", "봄감자는 언제 심나요?", ["파종", "춘작|봄", "월"]),
    ("potato", "감자 저장 온도는 몇 도인가요?", ["저장", "℃|\\d도", "큐어링|저장고"]),
    ("potato", "감자 더뎅이병은 어떻게 막나요?", ["더뎅이병", "방제|산도|pH"]),
    ("potato", "감자 비료는 얼마나 주나요?", ["시비량", "질소", "kg"]),
    ("potato", "씨감자는 어떻게 생산하나요?", ["씨감자", "무병|조직배양", "바이러스"]),
    ("potato", "감자 진딧물은 어떻게 방제하나요?", ["진딧물", "방제", "약제|살충"]),
    ("lettuce", "상추 씨앗이 잘 안 나는데 발아 온도가 몇 도인가요?", ["발아", "℃|\\d도"]),
    ("lettuce", "상추에 꽃대가 올라오는 이유가 뭔가요?", ["추대", "고온|장일"]),
    ("cucumber", "오이 생육에 알맞은 온도는?", ["℃", "생육", "낮|밤|야간"]),
    ("cucumber", "오이 암꽃은 어떻게 많이 달리게 하나요?", ["암꽃", "저온|단일|착생|분화"]),
]

MAX_GOLD = 6  # 정답 청크가 이보다 흔하면 어떤 설정이든 맞아서 변별력이 없다 — 스윕에서 뺀다.


def is_gold(text: str, pats: list[str]) -> bool:
    return all(re.search(p, text) for p in pats)


def build_chunks(target: int, max_chars: int) -> dict[str, list[dict]]:
    cc.TARGET_CHARS, cc.MAX_CHARS = target, max_chars
    out = {}
    for crop in cc.CROP_DIRS:
        recs = []
        for p in sorted((DATA / crop).glob("*.txt")):
            if not p.name.startswith("_"):
                recs.extend(cc.chunk_file(p, crop))
        out[crop] = recs
    return out


def embed_text(rec: dict, mode: str) -> str:
    if mode == "plain":
        return rec["content"]
    head = rec["doc_title"] + (f" > {rec['section']}" if rec.get("section") else "")
    return f"{head}\n{rec['content']}"


_cache: dict[str, list[float]] = {}


def load_cache() -> None:
    if CACHE.exists():
        with CACHE.open(encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                _cache[d["h"]] = d["v"]


def embed_all(texts: list[str], client: httpx.Client) -> None:
    todo = [t for t in dict.fromkeys(texts) if _h(t) not in _cache]
    if not todo:
        return
    with CACHE.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), 16):
            batch = todo[i : i + 16]
            r = client.post(
                f"{OLLAMA}/api/embed", json={"model": MODEL, "input": batch}, timeout=180
            )
            r.raise_for_status()
            for t, v in zip(batch, r.json()["embeddings"], strict=True):
                _cache[_h(t)] = v
                f.write(json.dumps({"h": _h(t), "v": v}) + "\n")
            print(f"  embed {i + len(batch)}/{len(todo)}", flush=True)


def _h(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))  # bge-m3는 정규화된 벡터


def norm(v: list[float]) -> list[float]:
    m = sum(x * x for x in v) ** 0.5
    return [x / m for x in v]


def main() -> None:
    load_cache()
    configs = [(400, 700), (700, 1200), (1000, 1600), (1400, 2200)]
    modes = ["plain", "titled"]
    ks = [3, 5, 8]

    with httpx.Client() as client:
        qv = {}
        embed_all([q for _, q, _ in QUERIES], client)
        for _, q, _ in QUERIES:
            qv[q] = norm(_cache[_h(q)])

        # gold 희소성 점검(현행 설정 기준)
        base = build_chunks(700, 1200)
        print("\n[gold 희소성] 질문별 정답 청크 수 / 작물 전체 청크 수 (x = 스윕 제외)")
        used = []
        for crop, q, gold in QUERIES:
            n = sum(1 for r in base[crop] if is_gold(r["content"], gold))
            ok = 0 < n <= MAX_GOLD
            print(f" {' ' if ok else 'x'}{n:3d}/{len(base[crop]):4d}  {crop:9s} {q[:34]}")
            if ok:
                used.append((crop, q, gold))
        print(f"  -> 스윕 대상 {len(used)}문항")

        print("\n[스윕] hit@k (정답 청크가 top-k 안에 하나라도 들어온 질문 비율)")
        print(f"{'config':>14} {'mode':>7} {'청크':>5} {'평균자':>6} " + " ".join(f"@{k}".rjust(6) for k in ks))
        for target, mx in configs:
            chunks = build_chunks(target, mx)
            for mode in modes:
                texts = [embed_text(r, mode) for crop in chunks for r in chunks[crop]]
                embed_all(texts, client)
                vecs = {crop: [norm(_cache[_h(embed_text(r, mode))]) for r in chunks[crop]] for crop in chunks}
                hits = {k: 0 for k in ks}
                for crop, q, gold in used:
                    scored = sorted(
                        range(len(chunks[crop])),
                        key=lambda i: -cos(qv[q], vecs[crop][i]),
                    )
                    for k in ks:
                        if any(is_gold(chunks[crop][i]["content"], gold) for i in scored[:k]):
                            hits[k] += 1
                total = sum(len(v) for v in chunks.values())
                avg = sum(r["char_count"] for c in chunks for r in chunks[c]) / total
                print(
                    f"{f'{target}/{mx}':>14} {mode:>7} {total:5d} {avg:6.0f} "
                    + " ".join(f"{hits[k] / len(used):6.2f}" for k in ks)
                )


if __name__ == "__main__":
    main()
