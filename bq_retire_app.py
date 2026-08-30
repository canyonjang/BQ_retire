import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="BQ(retire) · 은퇴와 상속설계", page_icon="🎯", layout="wide")

CLASSES = ["인하대", "숙대1", "숙대2"]
TABLE_PREFIX = "BQ(retire)_"
T_ACTIVE = TABLE_PREFIX + "active_session"
T_RESPONSES = TABLE_PREFIX + "responses"
T_STUDENTS = TABLE_PREFIX + "students"

WEEK_DATA = {
    2: [
        {
            "type": "balance", "id": 2101, "page": 1,
            "title": "은퇴설계의 출발점",
            "q": "은퇴설계를 시작한다면 나는 무엇을 먼저 하겠는가?",
            "opt": [
                "A: 은퇴할 때 필요한 목표자산 금액부터 계산한다.",
                "B: 은퇴 후 어떤 삶을 원하는지부터 구체적으로 그려본다."
            ],
            "note": "은퇴설계가 단순한 자금축적을 넘어 재무·비재무 목표를 함께 다룬다는 점을 연결합니다."
        },
        {
            "type": "balance", "id": 2102, "page": 1,
            "title": "30년의 생활비",
            "q": "65세부터 95세까지의 은퇴생활을 설계한다면 나는?",
            "opt": [
                "A: 매년 비슷한 생활비와 활동 수준을 전제로 계획한다.",
                "B: 활동기·회상기·간병기처럼 시기에 따라 지출의 성격이 달라질 가능성을 반영한다."
            ],
            "note": "활동기·회상기·간병기, go-go·slow-go·no-go의 의미를 토론하는 문항입니다."
        },
        {
            "type": "balance", "id": 2103, "page": 3,
            "title": "노후소득의 구조",
            "q": "노후생활비를 안정적으로 마련하는 방식으로 나는 어느 쪽이 더 마음에 드는가?",
            "opt": [
                "A: 가능한 한 큰 하나의 연금소득원에 집중한다.",
                "B: 공적연금·퇴직연금·개인연금 등 여러 소득원을 층층이 연결한다."
            ],
            "note": "국가-기업-개인의 다층 노후소득보장체계를 설명한 뒤 사용합니다."
        },
        {
            "type": "balance", "id": 2104, "page": 5,
            "title": "실물자산과 노후현금흐름",
            "q": "은퇴 후 소득이 부족하지만 주택이나 농지를 보유하고 있다면 나는?",
            "opt": [
                "A: 가능하면 실물자산은 그대로 보유·상속하고 다른 소득원을 찾는다.",
                "B: 요건이 맞는다면 주택연금·농지연금처럼 보유자산을 현금흐름으로 바꾸는 방법도 검토한다."
            ],
            "note": "1주차의 '집 vs 금융자산'과 달리, 이번에는 보유자산의 은퇴소득화가 논점입니다."
        },

        {
            "type": "quiz", "id": 2151, "page": 1,
            "q": "재무설계에서 은퇴를 가장 적절하게 이해한 것은?",
            "opt": [
                "A: 주된 직장에서 퇴직하는 한 번의 사건",
                "B: 가교직업·부분은퇴 등을 거쳐 완전은퇴로 이어질 수 있는 과정",
                "C: 소득활동이 완전히 끝난 뒤의 기간만을 뜻하는 상태",
                "D: 은퇴필요자금을 계산하는 재무활동만을 뜻하는 개념"
            ],
            "answer": "B",
            "explain": "강의안은 은퇴를 일회성 사건이 아니라 주된 일자리 이후 가교직업·부분은퇴 등을 거칠 수 있는 과정으로 설명합니다."
        },
        {
            "type": "quiz", "id": 2152, "page": 1,
            "q": "Stein의 노년기 생활기능 변화 3단계를 올바른 순서로 나열한 것은?",
            "opt": [
                "A: slow-go → go-go → no-go",
                "B: no-go → slow-go → go-go",
                "C: go-go → slow-go → no-go",
                "D: go-go → no-go → slow-go"
            ],
            "answer": "C",
            "explain": "활동적이고 건강한 go-go에서 활동이 줄어드는 slow-go, 자립생활이 어려운 no-go 순입니다."
        },
        {
            "type": "quiz", "id": 2153, "page": 2,
            "q": "현재 1억원의 구매력이 물가상승률 연 3%가 10년간 지속될 때, 10년 뒤 '현재가치 기준 구매력'은 약 얼마인가?",
            "opt": [
                "A: 7,440만원",
                "B: 8,500만원",
                "C: 1억원",
                "D: 1억 3,440만원"
            ],
            "answer": "A",
            "explain": "현재가치 기준 구매력은 1억원 ÷ 1.03^10 ≈ 7,441만원입니다. 계좌의 명목잔액이 자동으로 7,440만원이 된다는 뜻은 아닙니다."
        },
        {
            "type": "quiz", "id": 2154, "page": 2,
            "q": "가장 오래 근무한 일자리를 그만둔 평균연령 52.8세와 국민연금 수급개시연령 65세를 그대로 사용하면 두 시점의 차이는 약 얼마인가?",
            "opt": [
                "A: 7.2년",
                "B: 10.0년",
                "C: 12.2년",
                "D: 13.8년"
            ],
            "answer": "C",
            "explain": "65 − 52.8 = 12.2년입니다. '약 13년'이라고 하려면 퇴직연령을 52세로 단순화했다는 별도 설명이 필요합니다."
        },
        {
            "type": "quiz", "id": 2155, "page": 3,
            "q": "강의안에서 제시한 우리나라 다층 노후소득보장체계의 세 축은?",
            "opt": [
                "A: 공적연금·퇴직연금·개인연금",
                "B: 예금·주식·보험",
                "C: 국민연금·주택연금·농지연금",
                "D: 근로소득·사업소득·재산소득"
            ],
            "answer": "A",
            "explain": "국가의 공적연금, 기업·근로관계의 퇴직연금, 개인이 추가로 준비하는 개인연금이 기본 3층입니다."
        },
        {
            "type": "quiz", "id": 2156, "page": 5,
            "q": "2026년 현재 주택연금의 일반적인 기본 가입요건 설명으로 옳은 것은?",
            "opt": [
                "A: 부부 모두 65세 이상이고 1주택만 가능하다.",
                "B: 주택소유자 또는 배우자 중 1명이 55세 이상이고 부부합산 공시가격 등이 12억원 이하 요건을 본다.",
                "C: 주택소유자만 60세 이상이면 주택가격과 관계없이 가입할 수 있다.",
                "D: 배우자의 연령은 고려하지 않고 가입자 본인만 55세 이상이어야 한다."
            ],
            "answer": "B",
            "explain": "한국주택금융공사 기준으로 부부 중 1명이 55세 이상이고 부부합산 공시가격 등이 12억원 이하인 주택 보유 여부 등을 확인합니다."
        },
        {
            "type": "quiz", "id": 2157, "page": 5,
            "q": "농지연금의 담보농지 요건 중 2년 보유·거리 요건에 대한 설명으로 가장 정확한 것은?",
            "opt": [
                "A: 모든 담보농지는 취득 시점과 관계없이 반드시 2년 보유와 30km 이내를 모두 충족해야 한다.",
                "B: 2020년 1월 1일 이후 신규 취득 농지는 2년 보유 요건과 소재지·연접지역 또는 30km 이내 요건을 확인한다.",
                "C: 농지 보유기간은 필요 없고 주소지만 같은 시·도이면 된다.",
                "D: 5년 이상 보유한 농지만 가능하고 거리 요건은 없다."
            ],
            "answer": "B",
            "explain": "2020년 1월 1일 이후 신규 취득 농지에 2년 보유 및 거주·거리 요건이 적용됩니다."
        },
        {
            "type": "quiz", "id": 2158, "page": 6,
            "q": "은퇴 후 자산을 인출하면서 투자할 때 특히 주의해야 할 점으로 가장 적절한 것은?",
            "opt": [
                "A: 평균수익률만 같으면 수익률이 발생하는 순서는 중요하지 않다.",
                "B: 위험자산 비중이 높을수록 언제나 인출전략의 성공확률이 낮아진다.",
                "C: 은퇴 초기에 큰 손실이 나고 동시에 인출이 계속되면 이후 회복이 어려워질 수 있다.",
                "D: 물가상승은 은퇴 후 인출액 결정과 관계가 없다."
            ],
            "answer": "C",
            "explain": "은퇴 초기에 손실과 인출이 겹치면 회복에 참여할 자산이 줄어드는 '수익률 순서 위험'이 커질 수 있습니다."
        },
    ]
}


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


supabase: Client = init_connection()
PROF_PASSWORD = st.secrets.get("PROF_PASSWORD", "")


def get_session(class_name: str):
    rows = supabase.table(T_ACTIVE).select("*").eq("class_name", class_name).execute().data
    if not rows:
        supabase.table(T_ACTIVE).insert(
            {"class_name": class_name, "week_no": 2, "current_item_idx": 0, "is_open": False, "reveal": False}
        ).execute()
        return {"class_name": class_name, "week_no": 2, "current_item_idx": 0, "is_open": False, "reveal": False}
    return rows[0]


def set_session(class_name: str, **kwargs):
    row = {"class_name": class_name}
    row.update(kwargs)
    supabase.table(T_ACTIVE).upsert(row, on_conflict="class_name").execute()


def active_classes():
    rows = supabase.table(T_ACTIVE).select("*").eq("is_open", True).execute().data
    return [r["class_name"] for r in rows]


def add_student(class_name: str, name: str):
    supabase.table(T_STUDENTS).upsert(
        {"class_name": class_name, "name": name},
        on_conflict="class_name,name"
    ).execute()


def save_response(class_name, week_no, name, item, response, score):
    supabase.table(T_RESPONSES).upsert(
        {
            "class_name": class_name,
            "week_no": week_no,
            "name": name,
            "item_id": item["id"],
            "item_type": item["type"],
            "response": response,
            "score": float(score),
        },
        on_conflict="class_name,week_no,name,item_id"
    ).execute()


def my_response(class_name, week_no, name, item_id):
    rows = (
        supabase.table(T_RESPONSES).select("*")
        .eq("class_name", class_name)
        .eq("week_no", week_no)
        .eq("name", name)
        .eq("item_id", item_id)
        .execute().data
    )
    return rows[0] if rows else None


def item_responses(class_name, week_no, item_id):
    rows = (
        supabase.table(T_RESPONSES).select("*")
        .eq("class_name", class_name)
        .eq("week_no", week_no)
        .eq("item_id", item_id)
        .execute().data
    )
    return pd.DataFrame(rows)


def answer_letter(response: str) -> str:
    return (response or "").strip()[:1]


# ---------------- 로그인 ----------------
if "role" not in st.session_state:
    st.title("🎯 BQ(retire)")
    st.caption("은퇴와 상속설계 · LIVE 밸런스 게임 & 퀴즈")
    role = st.radio("접속 유형", ["학생", "교수"], horizontal=True)

    if role == "학생":
        name = st.text_input("이름")
        if st.button("입장하기", type="primary"):
            if not name.strip():
                st.error("이름을 입력해주세요.")
                st.stop()
            active = active_classes()
            if len(active) == 1:
                cn = active[0]
                add_student(cn, name.strip())
                st.session_state.update(role="student", name=name.strip(), class_name=cn)
                st.rerun()
            elif len(active) == 0:
                st.error("현재 열려 있는 강의실이 없습니다.")
            else:
                st.session_state["pending_name"] = name.strip()
                st.session_state["choose_class"] = True
                st.rerun()

        if st.session_state.get("choose_class"):
            cn = st.selectbox("열려 있는 분반", active_classes())
            if st.button("이 분반으로 입장"):
                nm = st.session_state.get("pending_name", "").strip()
                add_student(cn, nm)
                st.session_state.update(role="student", name=nm, class_name=cn)
                st.session_state.pop("choose_class", None)
                st.session_state.pop("pending_name", None)
                st.rerun()

    else:
        cn = st.selectbox("분반", CLASSES)
        pw = st.text_input("교수 비밀번호", type="password")
        if st.button("교수 통제소 입장", type="primary"):
            if PROF_PASSWORD and pw == PROF_PASSWORD:
                st.session_state.update(role="professor", class_name=cn)
                st.rerun()
            else:
                st.error("비밀번호가 틀렸거나 secrets에 PROF_PASSWORD가 설정되지 않았습니다.")
    st.stop()


my_class = st.session_state.class_name
session = get_session(my_class)
week_no = int(session.get("week_no", 2))
data = WEEK_DATA.get(week_no, [])
idx = min(int(session.get("current_item_idx", 0)), max(len(data) - 1, 0))
reveal = bool(session.get("reveal", False))
is_open = bool(session.get("is_open", False))

c1, c2 = st.columns([8, 2])
with c1:
    st.title("🎯 BQ(retire)")
    st.caption(f"{my_class} · {week_no}주차")
with c2:
    if st.button("로그아웃", use_container_width=True):
        st.session_state.clear()
        st.rerun()
st.write("---")


# ---------------- 학생 ----------------
if st.session_state.role == "student":
    me = st.session_state.name

    if not is_open:
        st.info("교수님이 BQ 세션을 열 때까지 기다려주세요.")
        st.stop()

    if not data:
        st.warning("이 주차 문항이 아직 등록되지 않았습니다.")
        st.stop()

    item = data[idx]
    st.caption(f"강의안 {item['page']}페이지 연계 · {idx + 1}/{len(data)}")
    st.subheader(item.get("title", "퀴즈") if item["type"] == "balance" else "Checkpoint Quiz")
    st.markdown(f"### {item['q']}")

    prev = my_response(my_class, week_no, me, item["id"])

    if prev:
        st.success("제출 완료")
        st.write(f"내 응답: **{prev['response']}**")
        if item["type"] == "quiz" and reveal:
            letter = answer_letter(prev["response"])
            if letter == item["answer"]:
                st.success("정답입니다.")
            else:
                st.error(f"정답은 {item['answer']}입니다.")
            st.info(item["explain"])
        elif item["type"] == "balance" and reveal:
            st.info(item["note"])
    else:
        with st.form(f"item_{item['id']}"):
            ans = st.radio("선택", item["opt"], index=None)
            submitted = st.form_submit_button("제출", type="primary")
            if submitted:
                if ans is None:
                    st.warning("응답을 선택해주세요.")
                else:
                    if item["type"] == "quiz":
                        score = 1.0 if answer_letter(ans) == item["answer"] else 0.0
                    else:
                        score = 1.0
                    save_response(my_class, week_no, me, item, ans, score)
                    st.rerun()

    if st.button("🔄 다음 문항 확인", use_container_width=True):
        st.rerun()


# ---------------- 교수 ----------------
else:
    st.subheader("교수 통제소")
    if not data:
        st.warning("문항 데이터가 없습니다.")
        st.stop()

    c1, c2, c3, c4 = st.columns([2, 5, 2, 2])
    c1.write(f"**{week_no}주차**")
    new_idx = c2.select_slider(
        "현재 문항",
        options=list(range(len(data))),
        value=idx,
        format_func=lambda i: f"{i+1}. p.{data[i]['page']} · {data[i]['q'][:34]}"
    )
    new_open = c3.toggle("학생 접속", value=is_open)
    if c4.button("✅ 적용", type="primary", use_container_width=True):
        set_session(
            my_class,
            week_no=week_no,
            current_item_idx=new_idx,
            is_open=new_open,
            reveal=False
        )
        st.rerun()

    item = data[idx]
    st.write("---")
    st.caption(f"강의안 {item['page']}페이지 연계")
    st.markdown(f"### {item['q']}")
    if item["type"] == "balance":
        st.info(item["note"])
    else:
        st.info(f"정답: {item['answer']} · {item['explain']}")

    df = item_responses(my_class, week_no, item["id"])
    if df.empty:
        st.warning("아직 제출된 응답이 없습니다.")
    else:
        st.metric("응답 인원", f"{len(df)}명")
        counts = df["response"].value_counts().reset_index()
        counts.columns = ["응답", "인원"]
        st.bar_chart(counts.set_index("응답"))

        if item["type"] == "quiz":
            correct = int((df["score"] == 1.0).sum())
            st.metric("정답률", f"{correct / len(df) * 100:.1f}%")
        else:
            a = int(df["response"].str.startswith("A").sum())
            b = int(df["response"].str.startswith("B").sum())
            st.write(f"A {a}명 · B {b}명")

    if item["type"] == "quiz":
        if st.button("📖 정답·해설 공개" if not reveal else "🙈 해설 닫기"):
            set_session(my_class, reveal=not reveal)
            st.rerun()
    else:
        if st.button("💬 교수 코멘트 공개" if not reveal else "🙈 코멘트 닫기"):
            set_session(my_class, reveal=not reveal)
            st.rerun()

    st.write("---")
    with st.expander("문항 목록 · 수업 위치"):
        st.dataframe(
            pd.DataFrame([
                {
                    "순서": i + 1,
                    "유형": x["type"],
                    "강의안 페이지": x["page"],
                    "문항": x["q"],
                }
                for i, x in enumerate(data)
            ]),
            use_container_width=True,
            hide_index=True
        )

    with st.expander("⚠️ 데이터 관리"):
        if st.button("현재 문항 응답 삭제"):
            (
                supabase.table(T_RESPONSES).delete()
                .eq("class_name", my_class)
                .eq("week_no", week_no)
                .eq("item_id", item["id"])
                .execute()
            )
            st.rerun()
        if st.button("이 분반 2주차 BQ 전체 초기화"):
            supabase.table(T_RESPONSES).delete().eq("class_name", my_class).eq("week_no", week_no).execute()
            supabase.table(T_STUDENTS).delete().eq("class_name", my_class).execute()
            set_session(my_class, week_no=2, current_item_idx=0, is_open=False, reveal=False)
            st.rerun()
