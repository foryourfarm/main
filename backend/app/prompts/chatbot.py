"""상담 챗봇(RAG) 프롬프트 템플릿 — 코드에 흩뿌리지 않고 여기서 버전 관리(CLAUDE.md §13).

설계 방향(nexttodo.md): 역할 지정 + 형식 지정(#명령문/#제약조건/#입력문/#출력형식) +
few-shot 고정. 정확성/환각 방지가 최우선이라 Chain-of-Thought·멀티 페르소나는 쓰지 않는다.

few-shot으로 고정한 세 가지 행동:
1. 근거 있고 작물 명확 -> 근거 기반 답변
2. 작물에 따라 답이 갈리는데 작물 불명확 -> 5종 중 무엇인지 되묻기(추측 금지)
3. 근거 없음 -> 지어내지 말고 전문가/농사로 안내로 거절

프롬프트를 바꾸면 PROMPT_VERSION을 올린다(품질 비교·재현용, docs/llm-integration.md §9).
"""

from dataclasses import dataclass
from decimal import Decimal

PROMPT_VERSION = "chatbot-v3"  # v2 -> v3: 로그인+밭이면 회원 밭 컨텍스트(작물/토양 추정치) 주입

CROPS = "사과·배·오이·감자·상추"

# 근거가 없어 답할 수 없을 때의 안내 문구 — 프롬프트(모델)와 코드 폴백이 같은 말을 하도록 한 곳에 둔다.
# 전문가 상담 + 농촌진흥청 농사로(농업기술포털) 유도(사용자 요청).
REFERRAL_TEXT = (
    "제공된 자료로는 확실히 답하기 어려워요. 정확한 정보는 농촌진흥청 농사로"
    "(www.nongsaro.go.kr)나 가까운 농업기술센터·전문가 상담을 이용해 주세요."
)

# 작물이 불명확할 때의 되묻기 문구 — few-shot과 코드가 같은 말을 하도록 공유.
ASK_CROP_TEXT = f"어떤 작물에 대한 질문인지 알려주시겠어요? 현재 {CROPS} 다섯 작물을 도와드릴 수 있어요."

_SYSTEM = f"""#명령문
너는 초보 귀농인을 돕는 친절한 재배 상담 전문가다. [입력문]의 참고자료와 이전 대화 맥락에 근거해서만 답한다.

#제약조건
- 참고자료에 없는 내용은 절대 지어내지 마라. 근거가 부족해 답할 수 없으면 다른 말 붙이지 말고 정확히 이렇게만 답하라: "{REFERRAL_TEXT}"
- 작물에 따라 답이 달라지는 질문인데 [작물]이 '(지정 안 됨)'이고 대화에서도 어떤 작물인지 알 수 없으면, 추측하지 말고 답하기 전에 이렇게 되물어라: "{ASK_CROP_TEXT}"
- EC, 유효인산 같은 전문용어는 초보자가 이해할 쉬운 말을 괄호로 병기하되 원래 의미를 왜곡하지 마라.
- [회원 밭 정보]가 주어지면 참고자료와 연결해 "회원님 밭 기준"으로 설명하라. 단 그 토양 수치는 추정치이며, 참고자료에 없는 임계값이나 좋다/나쁘다 판정을 지어내지 마라.
- 3~5문장으로 간결하게, 오늘 뭘 하면 되는지 행동 위주로 답하라.

#출력형식
평서형 한국어 문단."""

# few-shot: 위 세 가지 행동을 각각 한 예씩 고정.
_FEWSHOT = f"""#입력문
[작물] 상추
[참고자료]
- 상추는 서늘한 기후를 좋아하며 생육 적온은 15~20도다. 25도를 넘으면 잎이 쓴맛이 나고 웃자란다.

[질문]
요즘 낮에 28도까지 오르는데 괜찮을까요?

#출력
상추는 15~20도에서 잘 자라는 서늘한 작물이라 낮 28도는 조금 높은 편이에요. 잎이 쓴맛이 나거나 웃자랄 수 있으니 한낮에는 차광망을 씌워 온도를 낮춰 주세요. 물은 아침·저녁 서늘할 때 주는 게 좋아요.

#입력문
[작물] (지정 안 됨)
[참고자료]
- 작물별 적정 토양 산도(pH)는 종류에 따라 다르다.

[질문]
지금 밭 상태에 물을 얼마나 줘야 하나요?

#출력
{ASK_CROP_TEXT}

#입력문
[작물] 상추
[참고자료]
(관련 자료 없음)

[질문]
상추밭에 지렁이 분변토를 얼마나 넣어야 하나요?

#출력
{REFERRAL_TEXT}"""


@dataclass
class FarmContext:
    """프롬프트에 주입할 회원 밭 정보. 토양 수치는 soil_state의 추정치(is_estimated)다."""

    crop_id: int
    crop_name: str | None
    region_name: str | None
    days_since_planting: int
    soil_texture: str | None = None
    ph: Decimal | None = None
    ec: Decimal | None = None
    p2o5: Decimal | None = None
    organic_matter: Decimal | None = None


# 토양 지표 표시 순서·단위(ML 인계 §7.2: OM g/kg, 유효인산 mg/kg. pH·토성은 무단위/텍스트).
_SOIL_FIELDS: list[tuple[str, str, str]] = [
    ("ph", "pH", ""),
    ("ec", "EC", " dS/m"),
    ("p2o5", "유효인산", " mg/kg"),
    ("organic_matter", "유기물", " g/kg"),
    ("soil_texture", "토성", ""),
]


def format_farm_context(fc: FarmContext | None) -> str:
    """회원 밭 정보 -> 프롬프트 블록. 없으면 빈 문자열(비로그인/밭 없음 경로는 기존과 동일)."""
    if fc is None:
        return ""
    # 작물은 기존 #입력문의 [작물]로 표시(farm.crop_id로 자동설정) — 여기서 중복 표기하지 않는다.
    lines: list[str] = []
    if fc.region_name:
        lines.append(f"[지역] {fc.region_name}")
    lines.append(f"[파종 후 경과일] {fc.days_since_planting}일")
    soil = [
        f"{label} {getattr(fc, attr)}{unit}"
        for attr, label, unit in _SOIL_FIELDS
        if getattr(fc, attr) is not None
    ]
    lines.append(f"[토양(추정치)] {', '.join(soil) if soil else '정보 없음'}")
    return "#회원 밭 정보\n" + "\n".join(lines) + "\n\n"


def format_context(chunks: list[str]) -> str:
    """검색된 근거 조각을 프롬프트에 넣을 형태로. 없으면 few-shot과 같은 '(관련 자료 없음)' 마커."""
    if not chunks:
        return "(관련 자료 없음)"
    return "\n".join(f"- {c}" for c in chunks)


def format_crop(crop_name: str | None) -> str:
    """crop_id로 조회한 작물명. 없으면 few-shot과 같은 '(지정 안 됨)' 마커 -> 모델이 되묻게."""
    return crop_name or "(지정 안 됨)"


def format_history(history: list[tuple[str, str]] | None) -> str:
    """이전 대화 (role, content) 목록 -> 프롬프트 블록. 없으면 빈 문자열."""
    if not history:
        return ""
    lines = [f"{'사용자' if role == 'user' else '상담사'}: {content}" for role, content in history]
    return "[이전 대화]\n" + "\n".join(lines) + "\n\n"


def build_chat_prompt(
    question: str,
    chunks: list[str],
    history: list[tuple[str, str]] | None = None,
    crop_name: str | None = None,
    farm: "FarmContext | None" = None,
) -> str:
    """정형 근거(chunks) + 작물 + 회원 밭 정보 + 이전 대화 + 질문 -> 단일 프롬프트 문자열. 결정론적."""
    return (
        f"{_SYSTEM}\n\n"
        f"{_FEWSHOT}\n\n"
        f"{format_farm_context(farm)}"
        f"#입력문\n"
        f"{format_history(history)}"
        f"[작물] {format_crop(crop_name)}\n"
        f"[참고자료]\n{format_context(chunks)}\n\n"
        f"[질문]\n{question}\n\n"
        f"#출력\n"
    )
