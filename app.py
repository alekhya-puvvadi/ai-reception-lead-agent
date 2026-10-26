"""Streamlit interface for the AI Reception & Lead Management Agent."""

import json
import os
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

from agent import config, database as db
from agent.llm import AgentError, active_models, extract_lead, get_client, transcribe
from agent.sample_data import load_samples

st.set_page_config(page_title="Reception & Lead Agent", layout="wide")
db.init_db()

AUDIO_TYPES = ["mp3", "mp4", "m4a", "wav", "webm", "ogg", "flac", "mpeg", "mpga"]
RESULTS_DIR = config.BASE_DIR / "evaluation" / "results"


# ------------------------------------------------------------------ helpers
def api_key():
    return st.session_state.get("api_key_input") or os.getenv("GROQ_API_KEY")


@st.cache_resource
def cached_client(key: str):
    return get_client(key)


def label(value: str) -> str:
    return (value or "").replace("_", " ").capitalize()


def lead_card(lead: dict) -> None:
    title = f"{lead['lead_score']}  |  {lead['caller_name'] or 'Unknown caller'}  |  {lead['course_interest'] or label(lead['intent_type'])}"
    with st.expander(title):
        st.write(lead["summary"])
        st.caption(f"{label(lead['intent_type'])}, {lead['urgency']} urgency. {lead['lead_score_reason'] or ''}")
        st.markdown("**Suggested reply**")
        st.code(lead["suggested_reply"] or "", language="text", wrap_lines=True)


def bar(counts: dict, order: list = None, horizontal: bool = False) -> None:
    """Bar chart in the theme colour. `order` fixes the category order (otherwise most frequent first)."""
    keys = [k for k in (order or counts) if k in counts] if order else list(counts)
    frame = pd.DataFrame({"Category": keys, "Calls": [counts[k] for k in keys]})
    st.bar_chart(frame, x="Category", y="Calls", color="#0B6E6E", horizontal=horizontal,
                 sort=False, x_label="", y_label="Calls", height=280)


def format_received(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d %b, %H:%M")
    except (TypeError, ValueError):
        return value or ""


def empty_state() -> None:
    st.info("No calls yet. Analyse a call on the New call page, or load a few demo leads to explore the app.")
    if st.button("Load demo leads"):
        load_samples()
        st.rerun()


# ------------------------------------------------------------------ pages
def page_dashboard() -> None:
    st.title("Dashboard")
    stats = db.get_stats()
    if not stats["total"]:
        return empty_state()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calls analysed", stats["total"])
    c2.metric("High priority", stats["high_priority"], help=f"Lead score of {config.HIGH_PRIORITY_SCORE} or more")
    c3.metric("Average lead score", stats["avg_score"])
    c4.metric("Awaiting follow-up", stats["awaiting_follow_up"], help="Leads with status New")

    left, right = st.columns(2)
    with left:
        st.subheader("Calls by intent")
        bar({label(k): v for k, v in stats["by_intent"].items()}, horizontal=True)
    with right:
        st.subheader("Urgency and sentiment")
        a, b = st.columns(2)
        with a:
            bar(stats["by_urgency"], order=config.URGENCY_LEVELS)
        with b:
            bar(stats["by_sentiment"], order=config.SENTIMENTS)

    st.subheader("Follow up on these first")
    top = db.fetch_calls(statuses=["New", "Contacted"], min_score=config.HIGH_PRIORITY_SCORE, order="score", limit=5)
    if not top:
        st.caption("No high-priority leads are waiting.")
    for lead in top:
        lead_card(lead)


def run_analysis(source: str, audio=None, transcript: str = None) -> None:
    key = api_key()
    if not key:
        st.error("Add your Groq API key in the sidebar first. A free key is available at console.groq.com.")
        return
    try:
        client = cached_client(key)
        if audio is not None:
            with st.spinner("Transcribing the call..."):
                transcript = transcribe(client, *audio)
        with st.spinner("Analysing the call..."):
            info = extract_lead(client, transcript)
    except AgentError as exc:
        st.error(str(exc))
        return
    st.session_state["draft"] = {"id": uuid.uuid4().hex[:8], "source": source, "transcript": transcript, "info": info}


def render_draft() -> None:
    draft = st.session_state.get("draft")
    if not draft:
        return
    info, transcript, did = draft["info"], draft["transcript"], draft["id"]

    st.divider()
    st.subheader("Result")
    cols = st.columns(4)
    cols[0].metric("Intent", label(info["intent_type"]))
    cols[1].metric("Urgency", info["urgency"])
    cols[2].metric("Sentiment", info["sentiment"])
    cols[3].metric("Lead score", f"{info['lead_score']}/100")
    st.progress(info["lead_score"] / 100)
    st.caption(info["lead_score_reason"])
    st.write(info["summary"])
    if info["tags"]:
        st.caption("Tags: " + ", ".join(info["tags"]))
    with st.expander("Transcript"):
        st.write(transcript)

    with st.form(f"save_{did}"):
        left, right = st.columns(2)
        name = left.text_input("Caller name", value=info["caller_name"] or "", key=f"name_{did}")
        phone = right.text_input("Callback number", value=info["callback_number"] or "", key=f"phone_{did}")
        reply = st.text_area("Suggested reply", value=info["suggested_reply"], height=120, key=f"reply_{did}")
        saved = st.form_submit_button("Save lead", type="primary")
    if saved:
        record = {**info, "caller_name": name.strip() or None, "callback_number": phone.strip() or None,
                  "suggested_reply": reply.strip()}
        call_id = db.insert_call(transcript, record, source=draft["source"])
        st.session_state.pop("draft")
        st.session_state["flash"] = f"Saved lead #{call_id}."
        st.rerun()
    if st.button("Discard result", key=f"discard_{did}"):
        st.session_state.pop("draft")
        st.rerun()


def page_new_call() -> None:
    st.title("New call")
    if message := st.session_state.pop("flash", None):
        st.success(message)

    upload_tab, record_tab, text_tab = st.tabs(["Upload recording", "Record now", "Type transcript"])
    with upload_tab:
        file = st.file_uploader("Call recording", type=AUDIO_TYPES, help="mp3, m4a, wav and other common formats")
        if st.button("Analyse recording", type="primary", disabled=file is None, key="go_upload"):
            run_analysis("upload", audio=(file.getvalue(), file.name))
    with record_tab:
        recording = st.audio_input("Record the call with your microphone")
        if st.button("Analyse recording", type="primary", disabled=recording is None, key="go_record"):
            run_analysis("microphone", audio=(recording.getvalue(), "recording.wav"))
    with text_tab:
        text = st.text_area("Call transcript", height=160,
                            placeholder="Hi, my name is Priya. I'd like to join the Python course. Please call me tomorrow.")
        if st.button("Analyse transcript", type="primary", disabled=not text.strip(), key="go_text"):
            run_analysis("typed", transcript=text.strip())

    render_draft()


def lead_detail(call_id: int) -> None:
    lead = db.get_call(call_id)
    if not lead:
        return
    st.divider()
    st.subheader(f"Lead {lead['id']}: {lead['caller_name'] or 'Unknown caller'}")
    cols = st.columns(5)
    cols[0].metric("Lead score", lead["lead_score"])
    cols[1].metric("Intent", label(lead["intent_type"]))
    cols[2].metric("Urgency", lead["urgency"])
    cols[3].metric("Sentiment", lead["sentiment"])
    cols[4].metric("Callback number", lead["callback_number"] or "Not given")
    st.write(lead["summary"])
    st.caption(lead["lead_score_reason"] or "")
    st.markdown("**Suggested reply**")
    st.code(lead["suggested_reply"] or "", language="text", wrap_lines=True)
    with st.expander("Transcript"):
        st.write(lead["raw_transcript"])

    a, b, c = st.columns([2, 1, 2])
    current = config.STATUSES.index(lead["status"]) if lead["status"] in config.STATUSES else 0
    status = a.selectbox("Status", config.STATUSES, index=current, key=f"status_{call_id}")
    if b.button("Update status", key=f"update_{call_id}"):
        db.update_status(call_id, status)
        st.rerun()
    confirm = c.checkbox("Confirm deletion", key=f"confirm_{call_id}")
    if c.button("Delete lead", disabled=not confirm, key=f"delete_{call_id}"):
        db.delete_call(call_id)
        st.rerun()


def page_leads() -> None:
    st.title("Leads")
    f1, f2, f3, f4 = st.columns(4)
    search = f1.text_input("Search", placeholder="Name, course or keyword")
    intents = f2.multiselect("Intent", config.INTENTS, format_func=label)
    urgencies = f3.multiselect("Urgency", config.URGENCY_LEVELS)
    statuses = f4.multiselect("Status", config.STATUSES)
    min_score = st.slider("Minimum lead score", 0, 100, 0)

    calls = db.fetch_calls(intents, urgencies, statuses, min_score, search, order="score")
    if not calls:
        st.info("No leads match these filters.")
        return

    frame = pd.DataFrame(calls)
    view = frame[["id", "lead_score", "caller_name", "course_interest", "intent_type", "urgency",
                  "sentiment", "status", "created_at", "summary"]].copy()
    view["intent_type"] = view["intent_type"].map(label)
    view["created_at"] = view["created_at"].map(format_received)
    view[["caller_name", "course_interest"]] = view[["caller_name", "course_interest"]].fillna("Not given")
    event = st.dataframe(
        view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "lead_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "caller_name": st.column_config.TextColumn("Caller", width="medium"), "course_interest": "Course", "intent_type": "Intent",
            "urgency": "Urgency", "sentiment": "Sentiment", "status": "Status",
            "created_at": "Received", "summary": st.column_config.TextColumn("Summary", width="large"),
        },
    )
    st.download_button("Export to CSV", frame.drop(columns=["raw_transcript"]).to_csv(index=False),
                       file_name="leads.csv", mime="text/csv")

    rows = event.selection.rows
    if rows:
        lead_detail(int(view.iloc[rows[0]]["id"]))
    else:
        st.caption("Select a row to see the full lead, update its status or copy the suggested reply.")


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def page_evaluation() -> None:
    st.title("Evaluation")
    st.write("Accuracy of the pipeline against a labelled test set of scripted calls. "
             "Results appear here after you run `python -m evaluation.run_eval`.")
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No evaluation runs yet. From the project folder, run `python -m evaluation.run_eval`.")
        return

    choice = st.selectbox("Run", [f.stem for f in files])
    data = json.loads((RESULTS_DIR / f"{choice}.json").read_text(encoding="utf-8"))
    summary, meta = data["summary"], data["meta"]
    st.caption(f"{meta['mode']} mode, prompt {meta['prompt']}, {summary['n_cases']} cases, {meta['date']}")

    cols = st.columns(5)
    cols[0].metric("Intent accuracy", _pct(summary["intent_accuracy"]))
    cols[1].metric("Urgency accuracy", _pct(summary["urgency_accuracy"]))
    cols[2].metric("Valid JSON, first try", _pct(summary["first_attempt_json_rate"]))
    cols[3].metric("Pipeline success", _pct(summary["pipeline_success_rate"]))
    cols[4].metric("Average latency", f"{summary['avg_latency_s']} s")
    if "avg_wer" in summary:
        st.metric("Average word error rate (Whisper)", _pct(summary["avg_wer"]))

    st.subheader("By category")
    by_cat = pd.DataFrame([
        {"Category": label(cat), "Cases": s["n"], "Intent accuracy": _pct(s["intent_accuracy"]),
         "Urgency accuracy": _pct(s["urgency_accuracy"])}
        for cat, s in summary["by_category"].items()
    ])
    st.dataframe(by_cat, hide_index=True, width="stretch")

    bad = [c for c in data["cases"] if not (c["success"] and c["intent_correct"] and c["urgency_correct"])]
    st.subheader(f"Cases that failed ({len(bad)})")
    if bad:
        st.dataframe(pd.DataFrame([{
            "Case": c["id"], "Category": c["category"],
            "Intent (expected / got)": f"{c['expected_intent']} / {c.get('pred_intent')}",
            "Urgency (expected / got)": f"{c['expected_urgency']} / {c.get('pred_urgency')}",
            "Error": c.get("error") or "", "Transcript": c["reference_transcript"],
        } for c in bad]), hide_index=True, width="stretch")


def page_settings() -> None:
    st.title("Settings")
    st.subheader("Connection")
    models = active_models()
    st.write(f"Chat model: `{models['chat']}`  \nSpeech model: `{models['speech']}`  \nDatabase: `{config.DB_PATH}`")
    st.caption("If Groq retires a model, the app tries a fallback automatically. "
               "Set GROQ_CHAT_MODEL or GROQ_WHISPER_MODEL in .env to choose one yourself.")

    st.subheader("Data")
    if st.button("Load demo leads"):
        st.success(f"Added {load_samples()} demo leads.")
    st.write("")
    confirm = st.checkbox("I want to delete every saved lead")
    if st.button("Delete all leads", disabled=not confirm):
        db.delete_all()
        st.success("All leads deleted.")


# ------------------------------------------------------------------ layout
PAGES = {
    "Dashboard": page_dashboard,
    "New call": page_new_call,
    "Leads": page_leads,
    "Evaluation": page_evaluation,
    "Settings": page_settings,
}

with st.sidebar:
    st.header("Reception agent")
    page = st.radio("Go to", list(PAGES), label_visibility="collapsed")
    st.divider()
    if os.getenv("GROQ_API_KEY"):
        st.caption("Groq API key loaded from the environment.")
    else:
        st.text_input("Groq API key", type="password", key="api_key_input",
                      help="Free at console.groq.com. Kept only for this browser session.")

PAGES[page]()
