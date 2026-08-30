import pandas as pd
import streamlit as st
from supabase import create_client, Client

from bq_retire_questions import WEEK_DATA

st.set_page_config(page_title="BQ(retire) · 은퇴와 상속설계", page_icon="🎯", layout="wide")

CLASSES = ["인하대", "숙대1", "숙대2"]
TABLE_PREFIX = "BQ(retire)_"
T_ACTIVE = TABLE_PREFIX + "active_session"
T_RESPONSES = TABLE_PREFIX + "responses"
T_STUDENTS = TABLE_PREFIX + "students"


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


supabase: Client = init_connection()
PROF_PASSWORD = st.secrets.get("PROF_PASSWORD", "")


def available_weeks():
    return sorted(WEEK_DATA.keys())


def get_week_data(week_no: int):
    return WEEK_DATA.get(int(week_no), [])


def get_session(class_name: str):
    rows = supabase.table(T_ACTIVE).select("*").eq("class_name", class_name).execute().data
    if not rows:
        first_week = available_weeks()[0] if available_weeks() else 2
        supabase.table(T_ACTIVE).insert({
            "class_name": class_name,
            "week_no": first_week,
            "current_item_idx": 0,
            "is_open": False,
            "reveal": False,
        }).execute()
        return {
            "class_name": class_name,
            "week_no": first_week,
            "current_item_idx": 0,
            "is_open": False,
            "reveal": False,
        }
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
    supabase.table(T_RESPONSES).upsert({
        "class_name": class_name,
        "week_no": int(week_no),
        "name": name,
        "item_id": int(item["id"]),
        "item_type": item["type"],
        "response": response,
        "score": float(score),
    }, on_conflict="class_name,week_no,name,item_id").execute()


def my_response(class_name, week_no, name, item_id):
    rows = (
        supabase.table(T_RESPONSES).select("*")
        .eq("class_name", class_name)
        .eq("week_no", int(week_no))
        .eq("name", name)
        .eq("item_id", int(item_id))
        .execute().data
    )
    return rows[0] if rows else None


def item_responses(class_name, week_no, item_id):
    rows = (
        supabase.table(T_RESPONSES).select("*")
        .eq("class_name", class_name)
        .eq("week_no", int(week_no))
        .eq("item_id", int(item_id))
        .execute().data
    )
    return pd.DataFrame(rows)


def answer_letter(response: str) -> str:
    return (response or "").strip()[:1]


def item_label(item_idx: int, item: dict) -> str:
    kind = "밸런스" if item["type"] == "balance" else "퀴즈"
    return f"{item_idx + 1}번 · {kind}"


if "role" not in st.session_state:
    st.title("🎯 BQ(retire)")
    st.caption("은퇴와 상속설계 · LIVE 밸런스게임 & 퀴즈")
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
                st.error("비밀번호가 틀렸거나 Secrets에 PROF_PASSWORD가 설정되지 않았습니다.")
    st.stop()


my_class = st.session_state.class_name
session = get_session(my_class)

stored_week = int(session.get("week_no", available_weeks()[0] if available_weeks() else 2))
if stored_week not in WEEK_DATA and available_weeks():
    stored_week = available_weeks()[0]

week_no = stored_week
week_data = get_week_data(week_no)
stored_idx = int(session.get("current_item_idx", 0))
idx = min(stored_idx, max(len(week_data) - 1, 0))
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


if st.session_state.role == "student":
    me = st.session_state.name

    if not is_open:
        st.info("교수님이 BQ 세션을 열 때까지 기다려주세요.")
        st.stop()

    if not week_data:
        st.warning("이 주차 문항이 아직 등록되지 않았습니다.")
        st.stop()

    item = week_data[idx]
    st.caption(f"{week_no}주차 · {item_label(idx, item)}")
    st.subheader(item.get("title", "Checkpoint Quiz") if item["type"] == "balance" else "Checkpoint Quiz")
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
                    score = 1.0 if item["type"] == "balance" else (
                        1.0 if answer_letter(ans) == item["answer"] else 0.0
                    )
                    save_response(my_class, week_no, me, item, ans, score)
                    st.rerun()

    if st.button("🔄 다음 문항 확인", use_container_width=True):
        st.rerun()


else:
    st.subheader("교수 통제소")

    weeks = available_weeks()
    if not weeks:
        st.error("bq_retire_questions.py에 등록된 주차가 없습니다.")
        st.stop()

    selected_week = st.selectbox(
        "주차 선택",
        weeks,
        index=weeks.index(week_no) if week_no in weeks else 0,
        format_func=lambda w: f"{w}주차"
    )

    selected_data = get_week_data(selected_week)
    if not selected_data:
        st.warning(f"{selected_week}주차에 등록된 문항이 없습니다.")
        st.stop()

    default_idx = idx if selected_week == week_no else 0
    default_idx = min(default_idx, len(selected_data) - 1)

    selected_idx = st.selectbox(
        "문항 번호",
        options=list(range(len(selected_data))),
        index=default_idx,
        format_func=lambda i: item_label(i, selected_data[i])
    )
    selected_item = selected_data[selected_idx]

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        new_open = st.toggle("학생 접속", value=is_open)
    with c2:
        if st.button("✅ 주차·문항 적용", type="primary", use_container_width=True):
            set_session(
                my_class,
                week_no=int(selected_week),
                current_item_idx=int(selected_idx),
                is_open=bool(new_open),
                reveal=False
            )
            st.rerun()
    with c3:
        if st.button("🔄 현황 새로고침", use_container_width=True):
            st.rerun()

    st.write("---")
    kind_text = "밸런스게임" if selected_item["type"] == "balance" else "퀴즈"
    st.caption(f"{selected_week}주차 · {selected_idx + 1}번 · {kind_text} · 내부 ID {selected_item['id']}")
    st.markdown(f"### {selected_item['q']}")

    if selected_item["type"] == "balance":
        st.info(selected_item["note"])
    else:
        st.info(f"정답: {selected_item['answer']} · {selected_item['explain']}")

    df = item_responses(my_class, selected_week, selected_item["id"])

    if df.empty:
        st.warning("아직 제출된 응답이 없습니다.")
    else:
        st.metric("응답 인원", f"{len(df)}명")
        counts = df["response"].value_counts().reset_index()
        counts.columns = ["응답", "인원"]
        st.bar_chart(counts.set_index("응답"))

        if selected_item["type"] == "quiz":
            correct = int((df["score"] == 1.0).sum())
            st.metric("정답률", f"{correct / len(df) * 100:.1f}%")
        else:
            a = int(df["response"].str.startswith("A").sum())
            b = int(df["response"].str.startswith("B").sum())
            st.write(f"A {a}명 · B {b}명")

    current_matches_selection = (selected_week == week_no and selected_idx == idx)

    if not current_matches_selection:
        st.warning("현재 학생에게 송출 중인 문항과 위에서 선택한 문항이 다릅니다. 먼저 '주차·문항 적용'을 눌러주세요.")
    else:
        if selected_item["type"] == "quiz":
            if st.button("📖 정답·해설 공개" if not reveal else "🙈 해설 닫기"):
                set_session(my_class, reveal=not reveal)
                st.rerun()
        else:
            if st.button("💬 교수 코멘트 공개" if not reveal else "🙈 코멘트 닫기"):
                set_session(my_class, reveal=not reveal)
                st.rerun()

    st.write("---")

    with st.expander("전체 문항 목록"):
        rows = []
        for w in weeks:
            for i, x in enumerate(get_week_data(w)):
                rows.append({
                    "주차": w,
                    "문항번호": i + 1,
                    "유형": "밸런스게임" if x["type"] == "balance" else "퀴즈",
                    "내부 ID": x["id"],
                    "문항": x["q"],
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("⚠️ 데이터 관리"):
        if st.button("현재 선택 문항 응답 삭제"):
            (
                supabase.table(T_RESPONSES).delete()
                .eq("class_name", my_class)
                .eq("week_no", int(selected_week))
                .eq("item_id", int(selected_item["id"]))
                .execute()
            )
            st.rerun()

        if st.button(f"{selected_week}주차 BQ 응답 전체 삭제"):
            (
                supabase.table(T_RESPONSES).delete()
                .eq("class_name", my_class)
                .eq("week_no", int(selected_week))
                .execute()
            )
            st.rerun()
