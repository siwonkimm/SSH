import streamlit as st
import random
import time
from abc import ABC, abstractmethod


# =========================
# OOP 클래스 영역
# =========================

class ResumeValidationError(Exception):
    """이력서 입력값이 잘못되었을 때 발생하는 사용자 정의 예외"""
    pass


class Candidate:
    """지원자 클래스 — 이름, 성별, 억양, 출신, 경력, 전공 보유"""
    def __init__(self, name, gender, accent, background, experience, education):
        self.name = name
        self.gender = gender
        self.accent = accent
        self.background = background
        self.experience = experience
        self.education = education

    def __str__(self):
        return f"{self.name} | {self.gender} | {self.accent} | {self.background}"

    def __eq__(self, other):
        return self.name == other.name


class Resume:
    """이력서 클래스 — 지원자 정보를 감싸는 래퍼"""
    def __init__(self, candidate):
        if not candidate.name.strip():
            raise ResumeValidationError("이름을 입력해주세요.")

        if "미배정" in [
            candidate.gender,
            candidate.accent,
            candidate.background,
            candidate.experience,
            candidate.education
        ]:
            raise ResumeValidationError("모든 항목을 선택해주세요.")

        self.candidate = candidate

    def __str__(self):
        c = self.candidate
        return (f"[이력서] {c.name} / {c.gender} / {c.accent} / "
                f"{c.background} / {c.experience} / {c.education}")


class EvaluationResult:
    """평가 결과 클래스 — 공정 점수, 편향 감점, 항목별 상세 내역 포함"""
    def __init__(self, candidate, fairness_score, bias_score, details):
        self.candidate = candidate
        self.fairness_score = fairness_score
        self.bias_score = bias_score
        self.total_score = fairness_score - bias_score
        self.details = details

    def __lt__(self, other):
        return self.total_score < other.total_score

    def __gt__(self, other):
        return self.total_score > other.total_score

    def __str__(self):
        return f"{self.candidate.name}: {self.total_score}점 (공정 {self.fairness_score} / 편향감점 -{self.bias_score})"


class BiasRule:
    """편향 규칙 클래스 — 조건과 감점을 캡슐화"""
    def __init__(self, label, condition_fn, penalty, reason):
        self.label = label
        self.condition_fn = condition_fn
        self.penalty = penalty
        self.reason = reason

    def apply(self, candidate):
        if self.condition_fn(candidate):
            return self.penalty, self.reason
        return 0, None

    def __str__(self):
        return f"[편향규칙] {self.label} → -{self.penalty}점"


class FairEvaluator:
    """공정 평가자 — 경력과 전공만 보고 점수 계산"""

    def evaluate(self, resume):
        candidate = resume.candidate
        details = []

        fairness_score = 80

        if candidate.experience == "경력 많음":
            fairness_score += 12
            details.append(("경력 많음", +12, "fair", ""))
        elif candidate.experience == "경력 적음":
            fairness_score += 4
            details.append(("경력 적음", +4, "fair", ""))
        else:
            details.append(("신입", 0, "fair", ""))

        if candidate.education == "관련 전공":
            fairness_score += 8
            details.append(("관련 전공", +8, "fair", ""))
        elif candidate.education == "비전공":
            fairness_score += 1
            details.append(("비전공", +1, "fair", ""))

        return EvaluationResult(candidate, fairness_score, 0, details)


class BiasedEvaluator(FairEvaluator):
    """편향 평가자 — FairEvaluator를 상속받아 편향 감점을 추가"""

    BIAS_RULES = [
        BiasRule("성별 편향",        lambda c: c.gender == "여성",                    10, "여성이라는 이유로 감점 (남성 우대 정책)"),
        BiasRule("억양/말투 편향",   lambda c: c.accent in ["사투리", "외국어 억양"], 12, "표준어가 아니라는 이유로 감점"),
        BiasRule("지연(地緣) 편향",  lambda c: c.background == "지방 출신",           10, "지방 출신이라는 이유로 감점 (수도권 우대)"),
        BiasRule("학연(學緣) 편향",  lambda c: c.background == "비수도권 대학",        8, "비수도권 대학 출신이라는 이유로 감점"),
        BiasRule("성씨(혈연) 편향",  lambda c: not c.name.startswith("왕"),            6, "'왕'씨 성이 아니라는 이유로 감점 (사장 성씨 우대)"),
    ]

    def evaluate(self, resume):
        fair_result = super().evaluate(resume)

        candidate = resume.candidate
        fairness_score = fair_result.fairness_score
        details = fair_result.details

        bias_score = 0

        for rule in self.BIAS_RULES:
            penalty, reason = rule.apply(candidate)
            if penalty > 0:
                bias_score += penalty
                details.append((rule.label, -penalty, "bias", reason))

        return EvaluationResult(candidate, fairness_score, bias_score, details)


# =========================
# Streamlit 기본 설정
# =========================

st.set_page_config(page_title="SSH Careers", page_icon="💼", layout="wide")

for key, default in [
    ("page", "main"), ("results", []), ("latest_result", None),
    ("cv_name", ""), ("cv_gender", "미배정"), ("cv_accent", "미배정"),
    ("cv_background", "미배정"), ("cv_experience", "미배정"),
    ("cv_education", "미배정"), ("apply_step", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def go_page(p):
    st.session_state.page = p
    st.rerun()


# ── 전역 CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@300;400;700;900&family=Bebas+Neue&display=swap');

:root {
    --navy:#0a1628; --navy2:#0f2040;
    --blue:#1a4fa0; --blue2:#2563eb;
    --accent:#e8b400; --red:#dc2626; --red2:#ef4444;
    --white:#f0f4ff; --gray:#8899bb;
}
* { box-sizing:border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background:var(--navy) !important;
    color:var(--white) !important;
    font-family:'Noto Sans KR',sans-serif !important;
}
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stSidebarCollapsedControl"]
{ display:none !important; }

.block-container { padding:0 !important; max-width:100% !important; }

div.stButton > button {
    background:transparent !important;
    border:2px solid var(--accent) !important;
    color:var(--accent) !important;
    font-family:'Noto Sans KR',sans-serif !important;
    font-weight:700 !important; font-size:15px !important;
    border-radius:6px !important; padding:10px 20px !important;
    transition:all 0.25s ease !important; letter-spacing:1px !important;
    width:100% !important;
}
div.stButton > button:hover {
    background:var(--accent) !important; color:var(--navy) !important;
    box-shadow:0 0 24px rgba(232,180,0,0.5) !important;
}
div[data-testid="stTextInput"] input {
    background:rgba(255,255,255,0.05) !important;
    border:2px solid rgba(232,180,0,0.3) !important;
    color:var(--white) !important; border-radius:6px !important;
    font-family:'Noto Sans KR',sans-serif !important; font-size:16px !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color:var(--accent) !important;
    box-shadow:0 0 12px rgba(232,180,0,0.3) !important;
    outline:none !important;
}
div[data-testid="stTextInput"] label { color:var(--accent) !important; font-weight:700 !important; }

div[data-testid="stTextInput"] input::placeholder { color:rgba(240,244,255,0.35) !important; }

@keyframes fadeInUp   { from{opacity:0;transform:translateY(30px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeInDown { from{opacity:0;transform:translateY(-20px)} to{opacity:1;transform:translateY(0)} }
@keyframes slideInLeft  { from{opacity:0;transform:translateX(-40px)} to{opacity:1;transform:translateX(0)} }
@keyframes slideInRight { from{opacity:0;transform:translateX(40px)}  to{opacity:1;transform:translateX(0)} }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
@keyframes glowPulse { 0%,100%{box-shadow:0 0 20px rgba(232,180,0,0.3)} 50%{box-shadow:0 0 40px rgba(232,180,0,0.7)} }
@keyframes stamp {
    0%  { transform:scale(3) rotate(-15deg); opacity:0; }
    60% { transform:scale(0.95) rotate(-5deg); opacity:1; }
    80% { transform:scale(1.05) rotate(-5deg); }
    100%{ transform:scale(1) rotate(-5deg); opacity:1; }
}
@keyframes borderGlow { 0%,100%{border-color:rgba(220,38,38,0.4)} 50%{border-color:rgba(220,38,38,0.9)} }
</style>
""", unsafe_allow_html=True)


# =========================
# 메인 화면
# =========================

def main_page():
    st.markdown("""
<style>
.block-container { 
    padding:0 !important; 
}

html, body, [data-testid="stAppViewContainer"] {
    overflow:hidden !important; 
    height:100vh !important;
}

.st-key-ranking_btn {
    position: fixed !important;
    right: 44px !important;
    bottom: 137px !important;
    z-index: 99999 !important;
}

.st-key-apply_btn {
    position: fixed !important;
    right: 44px !important;
    bottom: 55px !important;
    z-index: 99999 !important;
}

.st-key-ranking_btn button,
.st-key-apply_btn button {
    width: 170px !important;
    height: 52px !important;
    background: rgba(0,0,0,0.2) !important;
    border: 2px solid #d4aa00 !important;
    border-radius: 7px !important;
    color: #d4aa00 !important;
    font-size: 17px !important;
    font-weight: bold !important;
    box-shadow: none !important;
}

.st-key-ranking_btn button:hover,
.st-key-apply_btn button:hover {
    background: rgba(0,0,0,0.2) !important;
    border: 2px solid #d4aa00 !important;
    color: #d4aa00 !important;
    box-shadow: none !important;
}

.st-key-ranking_btn button:focus,
.st-key-ranking_btn button:active,
.st-key-apply_btn button:focus,
.st-key-apply_btn button:active {
    background: rgba(0,0,0,0.2) !important;
    border: 2px solid #d4aa00 !important;
    color: #d4aa00 !important;
    box-shadow: none !important;
    outline: none !important;
}
</style>

<div style="position:fixed;inset:0;width:100vw;height:100vh;
     background:linear-gradient(160deg,#0a1628 0%,#0f2040 50%,#0a1628 100%);z-index:0;">
  <div style="position:absolute;inset:0;
       background-image:radial-gradient(rgba(255,255,255,0.08) 1px,transparent 1px);
       background-size:36px 36px;"></div>

  <div style="position:absolute;bottom:0;left:0;right:0;height:40%;
       background:linear-gradient(180deg,transparent,#0d1e3a 60%,#0a1628);"></div>

  <svg style="position:absolute;bottom:0;left:0;right:0;width:100%" viewBox="0 0 1440 220" preserveAspectRatio="none">
    <path d="M0,160 C360,220 1080,80 1440,160 L1440,220 L0,220 Z" fill="rgba(26,79,160,0.5)"/>
  </svg>

  <svg style="position:absolute;bottom:0;left:0;right:0;width:100%" viewBox="0 0 1440 200" preserveAspectRatio="none">
    <path d="M0,120 C480,180 960,60 1440,120 L1440,200 L0,200 Z" fill="rgba(10,22,40,0.8)"/>
  </svg>

  <div style="position:absolute;top:28px;left:36px;font-family:'Bebas Neue',sans-serif;
       font-size:22px;color:#e8b400;letter-spacing:4px;">
    [SSH careers]
  </div>

  <div style="position:absolute;top:34%;left:50%;transform:translateX(-50%);text-align:center;width:100%;">
    <div style="font-family:'Black Han Sans',sans-serif;font-size:clamp(56px,8vw,110px);
         color:#f0f4ff;letter-spacing:4px;line-height:1;
         text-shadow:0 0 60px rgba(26,79,160,0.8);">
      SSH 무역
    </div>
    <div style="font-size:clamp(14px,2vw,22px);color:#8899bb;margin-top:14px;letter-spacing:3px;">
      글로벌 무역의 미래, 함께 만들어갑니다
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    if st.button("채용 공고 / 랭킹", key="ranking_btn"):
        go_page("ranking")

    if st.button("이력서 제출", key="apply_btn"):
        go_page("apply")


# =========================
# 슬롯머신
# =========================

def slot_machine(options):
    placeholder = st.empty()
    speeds = [0.04,0.04,0.05,0.06,0.08,0.10,0.13,0.17,0.22,0.28,0.35]
    final = random.choice(options)
    for i, speed in enumerate(speeds):
        cur = random.choice(options)
        blur = max(0, (len(speeds)-i-1)*0.3)
        placeholder.markdown(f"""
<div style="margin:8px 0;padding:16px 20px;border-radius:12px;
     background:rgba(26,79,160,0.15);border:2px solid rgba(232,180,0,0.25);">
  <div style="font-size:10px;font-weight:700;letter-spacing:4px;color:var(--accent);
       margin-bottom:8px;text-align:center;animation:pulse 0.4s infinite;">◈ RANDOMIZING ◈</div>
  <div style="height:64px;border-radius:8px;background:var(--navy);
       border:1px solid rgba(232,180,0,0.15);
       display:flex;align-items:center;justify-content:center;
       font-size:28px;font-weight:900;color:white;filter:blur({blur:.1f}px);">{cur}</div>
</div>""", unsafe_allow_html=True)
        time.sleep(speed)

    placeholder.markdown(f"""
<div style="margin:8px 0;padding:16px 20px;border-radius:12px;
     background:rgba(232,180,0,0.12);border:3px solid var(--accent);
     animation:glowPulse 1.5s ease infinite;">
  <div style="font-size:10px;font-weight:700;letter-spacing:4px;color:var(--accent);
       margin-bottom:8px;text-align:center;">✦ SELECTED ✦</div>
  <div style="height:64px;border-radius:8px;
       background:linear-gradient(135deg,var(--blue),var(--blue2));
       display:flex;align-items:center;justify-content:center;
       font-size:30px;font-weight:900;color:white;">{final}</div>
</div>""", unsafe_allow_html=True)
    time.sleep(0.4)
    return final


# =========================
# 이력서 제출 화면
# =========================

def apply_page():
    st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{overflow-y:auto !important;height:auto !important;}
.block-container{padding:36px 48px !important;max-width:100% !important;}
</style>""", unsafe_allow_html=True)

    st.markdown("""
<div style="animation:fadeInDown 0.6s ease;margin-bottom:28px;">
  <div style="font-size:11px;letter-spacing:5px;color:var(--accent);margin-bottom:4px;font-weight:700;">SSH CAREERS</div>
  <div style="font-family:'Black Han Sans',sans-serif;font-size:36px;color:var(--white);letter-spacing:2px;">이력서 제출</div>
  <div style="width:52px;height:3px;background:var(--accent);margin-top:8px;border-radius:2px;"></div>
</div>""", unsafe_allow_html=True)

    steps = [
        ("cv_gender",     "성별",       ["여성", "남성"]),
        ("cv_accent",     "말투 / 억양", ["표준어", "사투리", "외국어 억양"]),
        ("cv_background", "출신 배경",   ["수도권 출신", "지방 출신", "비수도권 대학"]),
        ("cv_experience", "경력",        ["경력 많음", "경력 적음", "신입"]),
        ("cv_education",  "전공",        ["관련 전공", "비전공"]),
    ]

    left, right = st.columns([1, 1], gap="large")

    with left:
        field_map = [
            ("이름",      st.session_state.cv_name or "미입력"),
            ("성별",      st.session_state.cv_gender),
            ("말투/억양", st.session_state.cv_accent),
            ("출신 배경", st.session_state.cv_background),
            ("경력",      st.session_state.cv_experience),
            ("전공",      st.session_state.cv_education),
        ]

        rows_html = ""
        for label, val in field_map:
            assigned = val not in ["미배정", "미입력", ""]
            val_color = "#f0f4ff" if assigned else "rgba(240,244,255,0.25)"
            dot_color = "#e8b400" if assigned else "rgba(240,244,255,0.2)"
            dot = "◆" if assigned else "◇"
            rows_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:13px 0;border-bottom:1px solid rgba(255,255,255,0.07);font-size:15px;">'
                f'<span style="color:#8899bb;font-weight:700;font-size:13px;letter-spacing:1px;">{label}</span>'
                f'<span style="color:{val_color};font-weight:700;">'
                f'<span style="color:{dot_color};margin-right:5px;">{dot}</span>{val}</span></div>'
            )

        done = st.session_state.apply_step
        prog = int((done / len(steps)) * 100)

        st.markdown(
            f'<div style="animation:slideInLeft 0.6s ease;">'
            f'<div style="background:linear-gradient(160deg,rgba(26,79,160,0.15),rgba(10,22,40,0.8));'
            f'border:1px solid rgba(232,180,0,0.3);border-radius:16px;padding:28px 24px;'
            f'box-shadow:0 20px 60px rgba(0,0,0,0.5);">'
            f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:26px;letter-spacing:8px;'
            f'color:var(--accent);text-align:center;margin-bottom:6px;">이 력 서</div>'
            f'<div style="width:100%;height:1px;background:linear-gradient(90deg,transparent,var(--accent),transparent);'
            f'margin-bottom:18px;"></div>'
            f'{rows_html}'
            f'</div>'
            f'<div style="margin-top:16px;">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;'
            f'color:var(--gray);margin-bottom:6px;letter-spacing:1px;">'
            f'<span>진행도</span>'
            f'<span style="color:var(--accent);font-weight:700;">{done} / {len(steps)} 완료</span></div>'
            f'<div style="background:rgba(255,255,255,0.08);border-radius:4px;height:6px;overflow:hidden;">'
            f'<div style="width:{prog}%;height:100%;border-radius:4px;'
            f'background:linear-gradient(90deg,var(--blue),var(--accent));'
            f'transition:width 0.5s ease;box-shadow:0 0 10px rgba(232,180,0,0.5);"></div></div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    with right:
        st.session_state.cv_name = st.text_input(
            "지원자 이름", value=st.session_state.cv_name, placeholder="예: 김지원"
        )
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        if st.session_state.apply_step < len(steps):
            key, title, options = steps[st.session_state.apply_step]
            step_num = st.session_state.apply_step + 1
            st.markdown(
                f'<div style="background:rgba(26,79,160,0.15);border:1px solid rgba(232,180,0,0.2);'
                f'border-radius:12px;padding:18px 20px;margin-bottom:12px;">'
                f'<div style="font-size:10px;color:var(--accent);letter-spacing:3px;font-weight:700;margin-bottom:4px;">'
                f'STEP {step_num} / {len(steps)}</div>'
                f'<div style="font-size:20px;font-weight:900;color:var(--white);">{title} 선택</div>'
                f'<div style="font-size:12px;color:var(--gray);margin-top:3px;">랜덤 또는 직접 선택하세요</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            # ── 여기가 수정된 부분: 랜덤 선택 / 직접 선택 두 버튼 ──
            col_rand, col_direct = st.columns([1, 1], gap="small")

            with col_rand:
                if st.button(f"🎰 랜덤 선택", key=f"rand_{key}"):
                    result = slot_machine(options)
                    st.session_state[key] = result
                    st.session_state[f"show_direct_{key}"] = False
                    st.session_state.apply_step += 1
                    st.rerun()

            with col_direct:
                if st.button(f"✏️ 직접 선택", key=f"direct_toggle_{key}"):
                    st.session_state[f"show_direct_{key}"] = not st.session_state.get(f"show_direct_{key}", False)
                    st.rerun()

            # 직접 선택 패널 (토글)
            if st.session_state.get(f"show_direct_{key}", False):
                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                opt_cols = st.columns(len(options))
                for idx, opt in enumerate(options):
                    with opt_cols[idx]:
                        if st.button(opt, key=f"pick_{key}_{opt}"):
                            st.session_state[key] = opt
                            st.session_state[f"show_direct_{key}"] = False
                            st.session_state.apply_step += 1
                            st.rerun()
            # ── 수정 끝 ──

        else:
            st.markdown(
                '<div style="background:rgba(22,163,74,0.15);border:2px solid rgba(22,163,74,0.4);'
                'border-radius:12px;padding:20px;text-align:center;margin-bottom:12px;">'
                '<div style="font-size:28px;margin-bottom:6px;">✅</div>'
                '<div style="font-size:17px;font-weight:900;color:#4ade80;margin-bottom:3px;">모든 항목 입력 완료</div>'
                '<div style="font-size:12px;color:var(--gray);">최종 제출 버튼을 눌러주세요</div>'
                '</div>',
                unsafe_allow_html=True
            )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("↺ 초기화"):
                for k in ["cv_gender","cv_accent","cv_background","cv_experience","cv_education"]:
                    st.session_state[k] = "미배정"
                    st.session_state[f"show_direct_{k}"] = False
                st.session_state.apply_step = 0
                st.rerun()

        with c2:
            if st.button("← 메인"):
                go_page("main")

        with c3:
            if st.button("제출 →"):
                try:
                    candidate = Candidate(
                        st.session_state.cv_name,
                        st.session_state.cv_gender,
                        st.session_state.cv_accent,
                        st.session_state.cv_background,
                        st.session_state.cv_experience,
                        st.session_state.cv_education,
                    )

                    resume = Resume(candidate)

                    evaluator = BiasedEvaluator()
                    result = evaluator.evaluate(resume)

                    st.session_state.latest_result = result
                    st.session_state.results.append(result)

                    for k in ["cv_gender","cv_accent","cv_background","cv_experience","cv_education"]:
                        st.session_state[k] = "미배정"
                        st.session_state[f"show_direct_{k}"] = False

                    st.session_state.cv_name = ""
                    st.session_state.apply_step = 0

                    go_page("result")

                except ResumeValidationError as e:
                    st.warning(str(e))


# =========================
# 평가 결과 화면
# =========================

def result_page():
    st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{overflow-y:auto !important;height:auto !important;}
.block-container{padding:36px 48px !important;max-width:100% !important;}
</style>""", unsafe_allow_html=True)

    result = st.session_state.latest_result
    if result is None:
        st.warning("결과가 없습니다.")
        if st.button("메인으로"):
            go_page("main")
        return

    c = result.candidate
    passed = result.total_score >= 85

    if passed:
        banner_border = "rgba(22,163,74,0.5)"
        banner_bg     = "rgba(22,163,74,0.1)"
        stamp_color   = "#16a34a"
        stamp_text    = "합격"
        stamp_bg      = "rgba(22,163,74,0.12)"
        result_emoji  = "🎉"
    else:
        banner_border = "rgba(220,38,38,0.5)"
        banner_bg     = "rgba(220,38,38,0.08)"
        stamp_color   = "#dc2626"
        stamp_text    = "불합격"
        stamp_bg      = "rgba(220,38,38,0.12)"
        result_emoji  = "💀"

    banner_left, banner_right = st.columns([3, 1])
    with banner_left:
        st.markdown(
            f'<div style="background:{banner_bg};border:2px solid {banner_border};'
            f'border-radius:16px;padding:30px 32px;animation:fadeInUp 0.7s ease;margin-bottom:0;">'
            f'<div style="font-size:10px;color:var(--gray);letter-spacing:4px;font-weight:700;margin-bottom:8px;">'
            f'SSH 무역 — 채용 평가 결과</div>'
            f'<div style="font-family:\'Black Han Sans\',sans-serif;font-size:38px;color:var(--white);line-height:1.1;margin-bottom:6px;">'
            f'{c.name}<span style="font-size:22px;color:var(--gray);"> 님</span></div>'
            f'<div style="font-size:15px;color:var(--gray);">'
            f'{c.gender} &nbsp;·&nbsp; {c.accent} &nbsp;·&nbsp; {c.background}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with banner_right:
        st.markdown(
            f'<div style="background:{banner_bg};border:2px solid {banner_border};'
            f'border-radius:16px;height:100%;min-height:130px;'
            f'display:flex;align-items:center;justify-content:center;margin-bottom:0;">'
            f'<div style="border:4px solid {stamp_color};border-radius:50%;'
            f'width:110px;height:110px;display:flex;flex-direction:column;'
            f'align-items:center;justify-content:center;transform:rotate(-8deg);'
            f'background:{stamp_bg};animation:stamp 0.6s cubic-bezier(0.36,0.07,0.19,0.97) 0.3s both;">'
            f'<div style="font-size:26px;line-height:1;">{result_emoji}</div>'
            f'<div style="font-size:20px;font-weight:900;color:{stamp_color};letter-spacing:2px;">{stamp_text}</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    s1, s2, s3 = st.columns(3)

    def score_card(col, label, score_str, color, icon, subtitle):
        col.markdown(
            f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);'
            f'border-radius:14px;padding:24px 16px;text-align:center;position:relative;overflow:hidden;">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:3px;'
            f'background:linear-gradient(90deg,transparent,{color},transparent);"></div>'
            f'<div style="font-size:24px;margin-bottom:6px;">{icon}</div>'
            f'<div style="font-size:10px;color:var(--gray);letter-spacing:3px;font-weight:700;margin-bottom:8px;">{label}</div>'
            f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:52px;color:{color};line-height:1;">{score_str}</div>'
            f'<div style="font-size:13px;color:var(--gray);margin-top:2px;">점</div>'
            f'<div style="font-size:11px;color:var(--gray);margin-top:4px;">{subtitle}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    score_card(s1, "공정 평가", str(result.fairness_score), "#60a5fa", "📋", "역량 기반")
    score_card(s2, "편향 감점", f"-{result.bias_score}", "#f87171", "⚠️", "차별 요소")
    score_card(s3, "최종 점수", str(result.total_score),
               "#fbbf24" if passed else "#f87171", "🏁", "합격선: 85점")

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    st.markdown(
        '<div style="font-family:\'Black Han Sans\',sans-serif;font-size:20px;'
        'color:var(--white);letter-spacing:2px;margin-bottom:12px;">◈  평가 항목 상세</div>',
        unsafe_allow_html=True
    )

    for detail in result.details:
        label, delta, dtype, reason = detail
        if dtype == "fair":
            bg      = "rgba(37,99,235,0.1)"
            border  = "rgba(37,99,235,0.35)"
            badge_bg    = "rgba(37,99,235,0.3)"
            badge_color = "#93c5fd"
            badge_text  = "공정"
            delta_color = "#4ade80"
            delta_str   = f"+{delta}" if delta > 0 else str(delta)
            icon = "✅"
        else:
            bg      = "rgba(220,38,38,0.1)"
            border  = "rgba(220,38,38,0.35)"
            badge_bg    = "rgba(220,38,38,0.3)"
            badge_color = "#fca5a5"
            badge_text  = "편향"
            delta_color = "#f87171"
            delta_str   = str(delta)
            icon = "❌"

        reason_part = (
            f'<div style="font-size:12px;color:var(--gray);margin-top:2px;">→ {reason}</div>'
            if reason else ""
        )

        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'background:{bg};border:1px solid {border};border-radius:10px;'
            f'padding:13px 18px;margin-bottom:8px;">'
            f'<div style="display:flex;align-items:center;gap:12px;">'
            f'<div style="font-size:16px;">{icon}</div>'
            f'<div>'
            f'<div style="display:flex;align-items:center;gap:7px;">'
            f'<span style="background:{badge_bg};color:{badge_color};font-size:9px;'
            f'font-weight:700;letter-spacing:2px;padding:2px 7px;border-radius:4px;">{badge_text}</span>'
            f'<span style="font-size:15px;font-weight:700;color:var(--white);">{label}</span>'
            f'</div>'
            f'{reason_part}'
            f'</div></div>'
            f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:26px;'
            f'color:{delta_color};min-width:56px;text-align:right;">{delta_str}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    if result.bias_score > 0:
        bias_pct = round(result.bias_score / (result.fairness_score + result.bias_score) * 100)
        st.markdown(
            f'<div style="background:linear-gradient(135deg,rgba(220,38,38,0.1),rgba(10,22,40,0.9));'
            f'border:2px solid rgba(220,38,38,0.4);border-radius:14px;padding:22px 26px;'
            f'animation:borderGlow 2s infinite;">'
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">'
            f'<div style="font-size:22px;">🔍</div>'
            f'<div style="font-family:\'Black Han Sans\',sans-serif;font-size:18px;color:#ef4444;letter-spacing:1px;">'
            f'편향 분석</div></div>'
            f'<div style="font-size:15px;color:var(--white);line-height:1.8;margin-bottom:10px;">'
            f'<b style="color:var(--accent);">{c.name}</b>님 점수 중 '
            f'<b style="color:#f87171;font-size:20px;"> {bias_pct}%</b>가 '
            f'역량과 무관한 <b style="color:#f87171;">편향 요소</b>로 감점되었습니다.</div>'
            f'<div style="font-size:12px;color:var(--gray);border-top:1px solid rgba(255,255,255,0.08);'
            f'padding-top:10px;line-height:1.8;">'
            f'성별·억양·출신지·학벌·성씨에 의한 차별은 <b style="color:var(--accent);">고용상 차별금지법</b> 위반입니다.'
            f'</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("← 메인으로"):
            go_page("main")
    with c2:
        if st.button("📋 다음 지원자"):
            go_page("apply")
    with c3:
        if st.button("🏆 랭킹 보기"):
            go_page("ranking")


# =========================
# 채용 공고 + 랭킹 화면
# =========================

def ranking_page():
    st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{overflow-y:auto !important;height:auto !important;}
.block-container{padding:36px 48px !important;max-width:100% !important;}
</style>""", unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.markdown(
            '<div style="font-size:10px;letter-spacing:5px;color:var(--accent);margin-bottom:4px;font-weight:700;">SSH CAREERS</div>'
            '<div style="font-family:\'Black Han Sans\',sans-serif;font-size:34px;color:var(--white);letter-spacing:2px;margin-bottom:4px;">채용 공고</div>'
            '<div style="width:50px;height:3px;background:var(--accent);margin-bottom:22px;border-radius:2px;"></div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div style="background:linear-gradient(160deg,rgba(26,79,160,0.12),rgba(10,22,40,0.9));'
            'border:1px solid rgba(232,180,0,0.25);border-radius:16px;padding:28px 24px;">'
            '<div style="font-size:22px;font-weight:900;color:var(--accent);margin-bottom:3px;'
            'font-family:\'Black Han Sans\',sans-serif;letter-spacing:2px;">SSH 무역 채용 공고</div>'
            '<div style="font-size:12px;color:var(--gray);margin-bottom:16px;letter-spacing:1px;">'
            '"완전 공정한 기준으로 평가합니다 ㅎㅎ"</div>'
            '<div style="width:100%;height:1px;background:linear-gradient(90deg,var(--accent),transparent);'
            'margin-bottom:20px;opacity:0.4;"></div>',
            unsafe_allow_html=True
        )

        items = [
            ("1", "사장 이름: 왕하오", '"왕"씨 성씨에게 가산점 부여합니다^^', "⚠ 혈연·연고 채용 — 고용상 차별금지법 위반"),
            ("2", "힘 잘 쓰는 직원 우대합니다^^", "→ 남성 직원 우대 (여성 -10점)", "⚠ 성차별 채용 — 남녀고용평등법 위반"),
            ("3", "가족 같은 분위기 지향! 왕하오씨는 강원도 원주 출신", "→ 혈연·지연 우대 (지방/비수도권 출신 -8~10점)", "⚠ 지역 차별 — 국가인권위원회 시정 권고 대상"),
        ]

        for num, title, subtitle, warning in items:
            st.markdown(
                f'<div style="background:rgba(220,38,38,0.1);border:1px solid rgba(220,38,38,0.3);'
                f'border-radius:10px;padding:15px 16px;margin-bottom:12px;">'
                f'<div style="display:flex;align-items:flex-start;gap:12px;">'
                f'<div style="background:var(--red);color:white;font-weight:900;font-size:12px;'
                f'width:26px;height:26px;border-radius:50%;display:flex;align-items:center;'
                f'justify-content:center;flex-shrink:0;margin-top:2px;">{num}</div>'
                f'<div>'
                f'<div style="font-size:15px;font-weight:900;color:var(--white);margin-bottom:3px;">{title}</div>'
                f'<div style="font-size:13px;color:#fca5a5;font-weight:700;margin-bottom:2px;">{subtitle}</div>'
                f'<div style="font-size:10px;color:var(--gray);">{warning}</div>'
                f'</div></div></div>',
                unsafe_allow_html=True
            )

        st.markdown(
            '<div style="background:rgba(232,180,0,0.08);border:1px dashed rgba(232,180,0,0.4);'
            'border-radius:8px;padding:12px 16px;text-align:center;font-size:12px;'
            'color:var(--accent);font-weight:700;letter-spacing:1px;margin-bottom:16px;">'
            '⚠ 본 공고는 채용 편향을 시뮬레이션하기 위한 가상 자료입니다 ⚠</div>'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        if st.button("← 메인으로"):
            go_page("main")

    with right_col:
        st.markdown(
            '<div style="font-size:10px;letter-spacing:5px;color:var(--accent);margin-bottom:4px;font-weight:700;">LIVE RANKING</div>'
            '<div style="font-family:\'Black Han Sans\',sans-serif;font-size:34px;color:var(--white);letter-spacing:2px;margin-bottom:4px;">지원자 순위</div>'
            '<div style="width:50px;height:3px;background:var(--accent);margin-bottom:22px;border-radius:2px;"></div>',
            unsafe_allow_html=True
        )

        results = st.session_state.results

        if not results:
            st.markdown(
                '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);'
                'border-radius:14px;padding:56px 20px;text-align:center;">'
                '<div style="font-size:44px;margin-bottom:10px;opacity:0.4;">📭</div>'
                '<div style="font-size:15px;color:var(--gray);font-weight:700;">아직 제출된 지원자가 없습니다</div>'
                '<div style="font-size:12px;color:rgba(136,153,187,0.6);margin-top:5px;">'
                '이력서 제출 후 랭킹이 업데이트됩니다</div></div>',
                unsafe_allow_html=True
            )

            if st.button("📋 이력서 제출하기"):
                go_page("apply")

        else:
            sorted_results = sorted(results, reverse=True)
            avg_bias = round(sum(r.bias_score for r in results) / len(results), 1)
            passed_count = sum(1 for r in results if r.total_score >= 85)

            st.markdown(
                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:16px;">'
                f'<div style="background:rgba(37,99,235,0.15);border:1px solid rgba(37,99,235,0.3);'
                f'border-radius:10px;padding:12px;text-align:center;">'
                f'<div style="font-size:9px;color:var(--gray);letter-spacing:2px;margin-bottom:3px;">지원자</div>'
                f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:30px;color:#60a5fa;">{len(results)}</div></div>'
                f'<div style="background:rgba(22,163,74,0.12);border:1px solid rgba(22,163,74,0.3);'
                f'border-radius:10px;padding:12px;text-align:center;">'
                f'<div style="font-size:9px;color:var(--gray);letter-spacing:2px;margin-bottom:3px;">합격</div>'
                f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:30px;color:#4ade80;">{passed_count}</div></div>'
                f'<div style="background:rgba(220,38,38,0.12);border:1px solid rgba(220,38,38,0.3);'
                f'border-radius:10px;padding:12px;text-align:center;">'
                f'<div style="font-size:9px;color:var(--gray);letter-spacing:2px;margin-bottom:3px;">평균 편향 감점</div>'
                f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:30px;color:#f87171;">-{avg_bias}</div></div>'
                f'</div>',
                unsafe_allow_html=True
            )

            medals = ["🥇","🥈","🥉"]

            for i, r in enumerate(sorted_results):
                medal = medals[i] if i < 3 else f"#{i+1}"
                passed = r.total_score >= 85
                rc = "#4ade80" if passed else "#f87171"
                rb = "rgba(22,163,74,0.15)" if passed else "rgba(220,38,38,0.1)"
                bd = "rgba(22,163,74,0.4)" if passed else "rgba(220,38,38,0.25)"
                rl = "합격" if passed else "불합격"
                bar = max(0, min(100, r.total_score))

                bias_tags = ""
                for d in r.details:
                    if d[2] == "bias":
                        bias_tags += (
                            f'<span style="background:rgba(220,38,38,0.2);color:#fca5a5;'
                            f'font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;'
                            f'letter-spacing:1px;">{d[0]}</span> '
                        )

                bias_row = (
                    f'<div style="margin-top:4px;display:flex;gap:4px;flex-wrap:wrap;">{bias_tags}</div>'
                    if bias_tags else ""
                )

                st.markdown(
                    f'<div style="background:{rb};border:1px solid {bd};border-radius:12px;'
                    f'padding:13px 16px;margin-bottom:8px;position:relative;overflow:hidden;">'
                    f'<div style="position:absolute;bottom:0;left:0;width:{bar}%;height:3px;'
                    f'background:linear-gradient(90deg,{rc}44,{rc});"></div>'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;">'
                    f'<div style="display:flex;align-items:center;gap:10px;">'
                    f'<div style="font-size:20px;width:28px;text-align:center;">{medal}</div>'
                    f'<div>'
                    f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:2px;">'
                    f'<span style="font-size:15px;font-weight:900;color:var(--white);">{r.candidate.name}</span>'
                    f'<span style="background:rgba(232,180,0,0.15);color:var(--accent);font-size:9px;'
                    f'font-weight:700;padding:1px 6px;border-radius:4px;letter-spacing:1px;">{rl}</span>'
                    f'</div>'
                    f'<div style="font-size:10px;color:var(--gray);">'
                    f'{r.candidate.gender} · {r.candidate.accent} · {r.candidate.background}</div>'
                    f'{bias_row}'
                    f'</div></div>'
                    f'<div style="text-align:right;">'
                    f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:34px;color:{rc};line-height:1;">'
                    f'{r.total_score}</div>'
                    f'<div style="font-size:10px;color:var(--gray);">'
                    f'공정 {r.fairness_score} <span style="color:#f87171;">편향 -{r.bias_score}</span></div>'
                    f'</div></div></div>',
                    unsafe_allow_html=True
                )

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("📋 이력서 추가 제출"):
                    go_page("apply")
            with c2:
                if st.button("🗑 랭킹 초기화"):
                    st.session_state.results = []
                    st.session_state.latest_result = None
                    st.rerun()


# =========================
# 라우터
# =========================

page = st.session_state.page

if page == "main":
    main_page()
elif page == "apply":
    apply_page()
elif page == "result":
    result_page()
elif page == "ranking":
    ranking_page()
