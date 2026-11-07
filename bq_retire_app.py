import hashlib

import pandas as pd
import streamlit as st
from supabase import create_client, Client

import bq_retire_questions

WEEK_DATA = bq_retire_questions.WEEK_DATA

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


def all_sessions():
    rows = supabase.table(T_ACTIVE).select("*").execute().data
    return {r["class_name"]: r for r in rows}


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


# variants 필드가 있는 문항에서만 사용합니다. 일반 문항의 처리는 변경하지 않습니다.
# 이름·분반·문항 ID를 기반으로 조건을 안정적으로 배정합니다.
# 같은 학생이 새로고침하거나 재접속해도 동일 조건이 표시됩니다.
def assigned_variant(class_name: str, name: str, item: dict) -> str:
    key = f"{class_name}|{name}|{item['id']}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return "A" if digest[0] % 2 == 0 else "B"


def encode_variant_response(variant: str, answer: str) -> str:
    # 기존 Supabase 테이블 구조를 변경하지 않고 집단 정보를 함께 보관합니다.
    return f"VARIANT_{variant}|{answer}"


def decode_variant_response(response: str):
    if response and response.startswith("VARIANT_") and "|" in response:
        prefix, answer = response.split("|", 1)
        variant = prefix.removeprefix("VARIANT_")
        if variant in ("A", "B"):
            return variant, answer
    return None, response


if "role" not in st.session_state:
    st.title("🎯 BQ(retire)")
    st.caption("은퇴와 상속설계 · LIVE 밸런스게임 & 퀴즈")
    role = st.radio("접속 유형", ["학생", "교수"], horizontal=True)

    if role == "학생":
        active = active_classes()

        if not active:
            st.error("현재 열려 있는 강의실이 없습니다. 교수님이 세션을 열 때까지 기다려주세요.")
        else:
            # 분반은 항상 학생이 직접 고릅니다. 기본 선택값은 없습니다.
            cn = st.radio("분반을 선택하세요", active, index=None)
            name = st.text_input("이름")

            if st.button("입장하기", type="primary"):
                if cn is None:
                    st.error("분반을 선택해주세요.")
                elif not name.strip():
                    st.error("이름을 입력해주세요.")
                else:
                    add_student(cn, name.strip())
                    st.session_state.update(
                        role="student", name=name.strip(), class_name=cn
                    )
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

    st.info(f"**{my_class}** 분반으로 접속 중입니다. 분반이 다르면 로그아웃 후 다시 입장해주세요.")

    if not is_open:
        st.info("교수님이 BQ 세션을 열 때까지 기다려주세요.")
        st.stop()

    if not week_data:
        st.warning("이 주차 문항이 아직 등록되지 않았습니다.")
        st.stop()

    item = week_data[idx]
    st.caption(f"{week_no}주차 · {item_label(idx, item)}")
    st.subheader(item.get("title", "Checkpoint Quiz") if item["type"] == "balance" else "Checkpoint Quiz")
    variant = assigned_variant(my_class, me, item) if item.get("variants") else None
    question = item["variants"][variant]["q"] if variant else item["q"]
    st.markdown(f"### {question}")

    prev = my_response(my_class, week_no, me, item["id"])

    if prev:
        st.success("제출 완료")
        _, displayed_response = decode_variant_response(prev["response"])
        st.write(f"내 응답: **{displayed_response}**")

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
                    stored_answer = encode_variant_response(variant, ans) if variant else ans
                    save_response(my_class, week_no, me, item, stored_answer, score)
                    st.rerun()

    if st.button("🔄 다음 문항 확인", use_container_width=True):
        st.rerun()


else:
    st.subheader("교수 통제소")

    # ─────────────────────────────────────────
    # 분반 접속 현황
    # 다른 분반이 열려 있으면 학생이 잘못 입장할 수 있습니다.
    # ─────────────────────────────────────────
    sess_map = all_sessions()
    status_cols = st.columns(len(CLASSES))
    for col, c in zip(status_cols, CLASSES):
        opened = bool(sess_map.get(c, {}).get("is_open", False))
        mark = "🟢 열림" if opened else "⚪ 닫힘"
        col.write(f"**{c}** · {mark}" + ("  ← 현재 통제 중" if c == my_class else ""))

    others_open = [
        c for c in CLASSES
        if c != my_class and bool(sess_map.get(c, {}).get("is_open", False))
    ]
    if others_open:
        st.warning(
            f"다른 분반이 열려 있습니다: {', '.join(others_open)}. "
            "학생이 다른 분반으로 입장할 수 있습니다."
        )
        if st.button("🚪 다른 분반 모두 닫기", type="primary"):
            for c in others_open:
                set_session(c, is_open=False)
            st.rerun()

    st.write("---")

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
        # 토글은 누르는 즉시 DB에 반영됩니다.
        new_open = st.toggle("학생 접속", value=is_open, key=f"toggle_open_{my_class}")
        if bool(new_open) != is_open:
            set_session(my_class, is_open=bool(new_open))
            st.rerun()
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

    st.caption(
        f"{selected_week}주차 · {selected_idx + 1}번 · {kind_text} "
        f"· 내부 ID {selected_item['id']}"
    )

    # ─────────────────────────────────────────
    # 교수용 문항/정답 미리보기
    # 기본 상태에서는 강의실 화면에 보이지 않음
    # ─────────────────────────────────────────
    preview_key = f"prof_preview_{selected_week}_{selected_item['id']}"
    answer_key = f"prof_answer_{selected_week}_{selected_item['id']}"

    c_preview, c_answer = st.columns(2)

    with c_preview:
        if st.button(
            "👁 교수용 문항 보기"
            if not st.session_state.get(preview_key, False)
            else "🙈 교수용 문항 숨기기",
            use_container_width=True,
            key=f"btn_{preview_key}"
        ):
            st.session_state[preview_key] = not st.session_state.get(
                preview_key, False
            )
            st.rerun()

    with c_answer:
        if selected_item["type"] == "quiz":
            answer_label = (
                "🔐 교수용 정답·해설 보기"
                if not st.session_state.get(answer_key, False)
                else "🙈 교수용 정답·해설 숨기기"
            )
        else:
            answer_label = (
                "🔐 교수용 코멘트 보기"
                if not st.session_state.get(answer_key, False)
                else "🙈 교수용 코멘트 숨기기"
            )

        if st.button(
            answer_label,
            use_container_width=True,
            key=f"btn_{answer_key}"
        ):
            st.session_state[answer_key] = not st.session_state.get(
                answer_key, False
            )
            st.rerun()

    # 교수님이 문항 보기 버튼을 눌렀을 때만 표시
    if st.session_state.get(preview_key, False):
        st.markdown("#### 문항")
        if selected_item.get("variants"):
            for group in ("A", "B"):
                st.markdown(f"**{group}집단에 표시되는 질문**")
                st.markdown(selected_item["variants"][group]["q"])
        else:
            st.markdown(f"### {selected_item['q']}")

        for option in selected_item["opt"]:
            st.write(option)

    # 교수님이 별도로 버튼을 눌렀을 때만 정답/코멘트 표시
    if st.session_state.get(answer_key, False):

        if selected_item["type"] == "quiz":
            st.success(f"정답: {selected_item['answer']}")
            st.info(selected_item["explain"])

        else:
            st.info(selected_item["note"])

    df = item_responses(my_class, selected_week, selected_item["id"])

    if df.empty:
        st.warning("아직 제출된 응답이 없습니다.")
    else:
        st.metric("응답 인원", f"{len(df)}명")
        if selected_item.get("variants"):
            # 실험형 밸런스게임: 집단별 구매 의향 비교. 집단 A/B와 선택 A/B는 별개입니다.
            parsed = df["response"].apply(decode_variant_response)
            experiment_df = pd.DataFrame(parsed.tolist(), columns=["집단", "선택"])
            valid = experiment_df[experiment_df["집단"].isin(["A", "B"])].copy()
            valid["구매"] = valid["선택"].fillna("").str.startswith("A:")
            summary = []
            for group in ("A", "B"):
                grp = valid[valid["집단"] == group]
                n = len(grp)
                buyers = int(grp["구매"].sum())
                summary.append({
                    "집단": f"{group}집단",
                    "응답 인원": n,
                    "구매 인원": buyers,
                    "비구매 인원": n - buyers,
                    "구매율(%)": round(100 * buyers / n, 1) if n else None,
                })
            summary_df = pd.DataFrame(summary)
            st.markdown("#### 조건별 구매 의향 비교")
            st.dataframe(summary_df, hide_index=True, use_container_width=True)
            st.bar_chart(summary_df.set_index("집단")[["구매 인원", "비구매 인원"]])
            if len(valid) < len(df):
                st.caption(f"집단 정보가 없는 기존 응답 {len(df) - len(valid)}건은 집단별 비교에서 제외했습니다.")
            st.caption("집단 A는 단순 질문, 집단 B는 기회비용을 명시한 질문입니다. 구매율은 응답 인원 기준이며, 소규모 차이는 일반화할 수 없습니다.")
        else:
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