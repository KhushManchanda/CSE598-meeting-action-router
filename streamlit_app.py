"""Local Streamlit application; launch with python run_ui.py.

Startup and the offline walkthrough do not load .env. API runs require an
explicit in-app configuration consent and a deliberate Start action.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from ui import demo
from ui.runtime import CONFIG_NAMES, MODES, ROOT, RUNS, RunController, RunRequest, load_history, read_local_config

st.set_page_config(page_title="Action Router · Meeting workspace", page_icon="↗", layout="wide")
st.markdown("""<style>
html,body,[class*="css"],.stApp{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.stApp{background:#f6f7f9;color:#192b3c;}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e3e8ed;}
.block-container{max-width:1240px;padding-top:2.6rem;padding-bottom:4rem;}
h1{font-size:2.35rem!important;letter-spacing:-.07rem;font-weight:700!important;}
h2{font-size:1.45rem!important;letter-spacing:-.03rem;}
h3{font-size:1.05rem!important;}
[data-testid="stMetric"]{background:white;border:1px solid #e3e8ed;border-radius:12px;padding:16px;}
[data-testid="stMetricValue"]{font-size:1.8rem;}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:12px;}
[data-testid="stForm"]{background:#fff;border:1px solid #e0e6eb;border-radius:14px;padding:1.35rem;}
div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"]{background:#12695e;border-color:#12695e;}
.eyebrow{font-size:.72rem;letter-spacing:.12rem;font-weight:700;color:#627787;margin-bottom:.7rem;}
.brand{display:flex;align-items:center;gap:11px;font-size:1.1rem;font-weight:750;margin:0 0 28px;}
.brand-icon{background:#12695e;color:#fff;border-radius:11px;padding:5px 12px;font-size:1.45rem;}
.stepbar{display:flex;gap:7px;margin:20px 0 25px;flex-wrap:wrap;}
.step{padding:8px 15px;border-radius:25px;border:1px solid #dfe6ea;background:white;font-size:.79rem;color:#617685;}
.step.active{background:#e0f1eb;color:#0d5e51;border-color:#b7d9cd;font-weight:650;}
.status{font-size:.72rem;border-radius:5px;padding:4px 8px;background:#e0f1eb;color:#0d5e51;letter-spacing:.04rem;}
.footnote{color:#72818e;font-size:.77rem;margin-top:35px;}
.stTextArea textarea{line-height:1.65;font-size:.91rem;}
</style>""", unsafe_allow_html=True)


def active_controller():
    return st.session_state.get("run_controller")


def running(controller=None):
    controller = controller or active_controller()
    return bool(controller and controller.snapshot()["status"] in ("running", "awaiting_review"))


def navigate(page):
    st.session_state["next_page"] = page


if "next_page" in st.session_state:
    st.session_state["workspace_nav"] = st.session_state.pop("next_page")

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-icon">↗</span>Action Router</div>', unsafe_allow_html=True)
    st.caption("GROUP 30 · MEETING WORKSPACE")
    page = st.radio("Workspace", ["New meeting", "Current run", "Run history", "Evaluation", "Connections"],
                    key="workspace_nav", label_visibility="collapsed")
    st.divider()
    mode = st.selectbox("Runtime", MODES, key="runtime_mode", disabled=running())
    if mode == MODES[0]:
        st.caption("Scripted model · simulated tools\n\nNo API keys or paid requests.")
    elif mode == MODES[1]:
        st.caption("Real OpenAI reasoning · simulated tools. Model usage is billed; accounts are unchanged.")
    else:
        st.caption("Real OpenAI reasoning · connected accounts. Each write needs your approval.")
    if mode != MODES[0]:
        st.checkbox("Allow this app to read local .env for API runs", key="allow_local_config", disabled=running())
        with st.expander("What configuration is used?"):
            st.write("Only this repository’s .env is read when you start an API run or check connections. Values remain on this local server; keys are never shown or saved in run exports.")
            st.code(", ".join(CONFIG_NAMES), language=None)
    st.divider()
    st.caption("HUMAN REVIEW FIRST")
    st.caption("Source evidence stays beside every proposal. Gmail creates drafts only.")
    st.markdown('<div class="footnote">Local workspace · America/Phoenix<br>CLI and original datasets remain available.</div>', unsafe_allow_html=True)


def samples():
    choices = {
        "Trello checklist · Live demo": ("data/demo/arjun_trello/transcript_full_run.txt", "data/demo/arjun_trello/roster.json", "2026-11-03"),
        "Calendar rehearsal · Live demo": ("data/demo/arjun_google/calendar.txt", "data/demo/arjun_google/roster.json", "2026-11-03"),
        "Gmail agenda · Live demo": ("data/demo/arjun_google/gmail.txt", "data/demo/arjun_google/roster.json", "2026-11-03"),
    }
    for folder in sorted((ROOT / "data/synthetic").iterdir()):
        if folder.is_dir() and (folder / "meta.json").exists():
            meta = json.loads((folder / "meta.json").read_text())
            label = folder.name.removeprefix("synth_").replace("_", " ").title() + " · Synthetic"
            choices[label] = (str(folder / "transcript.txt"), str(folder / "roster.json"), meta["meeting_date"])
    return choices


def new_meeting():
    st.markdown('<div class="eyebrow">MEETING WORKSPACE / NEW MEETING</div>', unsafe_allow_html=True)
    st.title("Review your meeting actions")
    st.write("Bring the conversation. Review the commitments. Follow through in the right tools.")
    st.markdown('<div class="stepbar"><span class="step active">01 · Set up meeting</span><span class="step">02 · Review actions</span><span class="step">03 · Verify results</span></div>', unsafe_allow_html=True)
    offline = mode == MODES[0]
    if offline:
        title, text, roster, meeting_date = "Weekly project sync", demo.TRANSCRIPT, demo.ROSTER, demo.MEETING_DATE
        source_key = "offline"
        st.info("Offline walkthrough: three scripted proposals exercise the real validation, approval, ledger, and mock-tool pipeline. Choose an OpenAI mode to process your own transcript.")
    else:
        source = st.radio("Transcript source", ["Built-in meeting", "Upload .txt", "Paste transcript"], horizontal=True)
        if source == "Built-in meeting":
            options = samples()
            label = st.selectbox("Choose a meeting", list(options))
            transcript_path, roster_path, meeting_date = options[label]
            title, source_key = label.split(" · ")[0], label
            text = (ROOT / transcript_path).read_text()
            roster = json.loads((ROOT / roster_path).read_text())
        else:
            title, text, roster = "My meeting", "", [{"name": "", "aliases": [], "email": "", "trello_member_id": ""}]
            meeting_date = datetime.now(ZoneInfo("America/Phoenix")).date().isoformat()
            source_key = source
            if source == "Upload .txt":
                upload = st.file_uploader("Speaker-labeled transcript", type=["txt"])
                if upload:
                    try:
                        text = upload.getvalue().decode("utf-8-sig")
                        source_key += upload.name
                    except UnicodeDecodeError:
                        st.error("Upload a UTF-8 text file.")
            roster_upload = st.file_uploader("Participant roster JSON (optional)", type=["json"])
            if roster_upload:
                try:
                    roster = json.loads(roster_upload.getvalue())
                    if not isinstance(roster, list) or any(not isinstance(row, dict) for row in roster):
                        raise ValueError
                    source_key += roster_upload.name
                except (ValueError, UnicodeDecodeError):
                    st.error("Roster JSON must be an array of participant objects.")
                    return
    with st.form("meeting_setup", clear_on_submit=False):
        left, right = st.columns([2, 1])
        with left:
            name = st.text_input("Meeting title", value=title, key=f"title_{source_key}")
        with right:
            meeting_day = st.date_input("Meeting date", value=date.fromisoformat(meeting_date),
                                        disabled=offline, key=f"date_{source_key}")
        st.subheader("Conversation")
        transcript = st.text_area("Transcript", value=text, height=260, disabled=offline,
                                  key=f"transcript_{source_key}", help="One speaker turn per line: Name: utterance.")
        st.subheader("People and identities")
        st.caption("Names and aliases identify the owner. Real email addresses and Trello member IDs are needed for live actions; synthetic rosters use placeholders.")
        table = [{"name": p.get("name", ""), "aliases": ", ".join(p.get("aliases") or []) if isinstance(p.get("aliases"), list) else p.get("aliases", ""),
                  "email": p.get("email", ""), "trello_member_id": p.get("trello_member_id", "")} for p in roster]
        edited_roster = st.data_editor(table, num_rows="fixed" if offline else "dynamic", disabled=offline,
            key=f"roster_{source_key}", use_container_width=True, hide_index=True,
            column_config={"name": "Name", "aliases": "Aliases (comma-separated)", "email": "Email", "trello_member_id": "Trello member ID"})
        budget = st.number_input("Execution attempt budget", min_value=1, max_value=200, value=40,
                                 help="The backend counts creation attempts. Resolver calls and read-backs are excluded, and a retry sequence can exceed the remaining budget.")
        live_confirmed = True
        if mode == MODES[2]:
            live_confirmed = st.checkbox("Use my connected test accounts. I will approve each proposed write.")
            st.caption("Calendar defaults to 10:00–10:30 and Trello to 17:00 for date-only deadlines, in America/Phoenix. Gmail drafts are never sent.")
        start = st.form_submit_button("Extract actions →", type="primary", disabled=running(), use_container_width=True)
    if running():
        st.caption("A run is already active. Continue its review in Current run.")
    if start:
        try:
            if not live_confirmed:
                raise ValueError("Confirm use of your connected test accounts before starting a live run.")
            config = {} if offline else read_local_config(st.session_state.get("allow_local_config", False))
            controller = RunController(RunRequest(name, transcript, meeting_day.isoformat(), list(edited_roster), mode, int(budget)), config)
            controller.start()
            st.session_state["run_controller"] = controller
            navigate("Current run")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))


def metrics(state):
    actions = state.get("actions", [])
    verified = sum(a["state"] == "verified" for a in actions)
    escalated = sum(a["state"] == "escalated" for a in actions)
    rejected = sum(a["state"] == "rejected" for a in actions)
    cols = st.columns(4)
    for col, label, value in zip(cols, ["Actions found", "Verified", "Needs follow-up", "Model cost"],
                                 [len(actions), verified, escalated, f"${state.get('cost', 0):.6f}"]):
        col.metric(label, value)
    if rejected:
        st.caption(f"{rejected} action(s) rejected without execution.")


def review_form(controller, pending):
    st.subheader("Ready for your review")
    st.caption("Nothing is executed until you approve. Edits are checked again before execution.")
    left, right = st.columns([1.35, 1])
    with right:
        with st.container(border=True):
            st.markdown("**Source evidence**")
            ids = pending["evidence_utterance_ids"]
            for utterance in pending["evidence"]:
                st.caption(f"{utterance['id']} · {utterance['speaker']}" + (" · cited" if utterance["id"] in ids else ""))
                st.write(utterance["text"])
            if pending.get("notes"):
                st.caption(pending["notes"])
    with left:
        with st.form(f"review_{pending['id']}"):
            task = st.text_input("Subject / task title", pending["task"])
            owners = [p["name"] for p in controller.request.roster]
            owner = st.selectbox("Responsible owner", owners, index=owners.index(pending["owner"]) if pending["owner"] in owners else 0)
            destinations = ["trello_task", "calendar_event", "email_draft"]
            tool = st.selectbox("Destination", destinations, index=destinations.index(pending["tool"]),
                                format_func=lambda value: {"trello_task": "Trello task", "calendar_event": "Calendar event", "email_draft": "Gmail draft"}[value])
            due = st.text_input("Due date (YYYY-MM-DD, optional)", pending.get("due") or "")
            recipients = st.text_input("Attendee / recipient emails (comma-separated)", ", ".join(pending["attendees_or_recipients"]))
            body = st.text_area("Email body / description", pending["description"], height=210)
            approve_col, reject_col = st.columns(2)
            approve = approve_col.form_submit_button("Approve action", type="primary", use_container_width=True)
            reject = reject_col.form_submit_button("Reject action", use_container_width=True)
        if approve or reject:
            try:
                values = {"task": task, "owner": owner, "tool": tool, "due": due.strip() or None,
                          "attendees_or_recipients": [part.strip() for part in recipients.split(",") if part.strip()],
                          "description": body}
                edits = {key: value for key, value in values.items() if value != pending.get(key)}
                if controller.submit(pending["id"], bool(approve), edits if approve else {}):
                    st.rerun()
            except ValueError:
                st.error("Use a valid YYYY-MM-DD date, or leave the due date blank.")


def action_results(state):
    actions = state.get("actions", [])
    reviewed = state.get("reviewed", {})
    escalations = {item["id"]: item for item in (state.get("report") or {}).get("escalated", [])}
    if not actions:
        return
    st.subheader("Action ledger")
    for row in actions:
        item = {**row, **reviewed.get(row["id"], {}), "state": row["state"]}
        with st.expander(f"{item['state'].replace('_', ' ').title()} · {item.get('task') or 'Untitled action'}"):
            st.write(f"**Owner:** {item.get('owner') or 'Unresolved'} · **Destination:** {item.get('tool') or 'Unresolved'} · **Due:** {item.get('due') or 'Not specified'}")
            if item.get("description"):
                st.write(item["description"])
            if row.get("escalation_reason") or row.get("execution_error"):
                st.warning(row.get("escalation_reason") or row["execution_error"])
            details = escalations.get(row["id"], {})
            if details.get("mismatches"):
                st.write("Read-back differences:")
                st.json(details["mismatches"])
            record = row.get("created_object") or details.get("created_object")
            if record:
                if state["mode"] == MODES[2] and record.get("id"):
                    if item.get("tool") == "trello_task":
                        st.link_button("Open Trello card", f"https://trello.com/c/{record['id']}")
                    elif item.get("tool") == "email_draft":
                        st.link_button("Open Gmail drafts", "https://mail.google.com/mail/u/0/#drafts")
                    elif item.get("tool") == "calendar_event":
                        st.link_button("Open Google Calendar", "https://calendar.google.com/")
                st.json(record)


def run_view():
    controller = active_controller()
    st.markdown('<div class="eyebrow">MEETING WORKSPACE / REVIEW & RESULTS</div>', unsafe_allow_html=True)
    if not controller:
        st.title("Your review queue")
        st.info("Start a meeting to extract and review its actions.")
        st.button("Set up a meeting", on_click=navigate, args=("New meeting",), type="primary")
        return
    initial = controller.snapshot()
    st.title(initial["title"])
    st.caption(f"{initial['mode']} · Meeting {controller.request.meeting_date} · {controller.id}")

    @st.fragment(run_every=1 if running(controller) else None)
    def live_panel():
        state = controller.snapshot()
        metrics(state)
        st.markdown(f'<div class="stepbar"><span class="step active">{escape(state["stage"])}</span><span class="step">{state["model_calls"]} model calls · {state["tokens"]} tokens</span></div>', unsafe_allow_html=True)
        if state["mode"] == MODES[0]:
            st.caption("Offline walkthrough · all model responses are scripted and all writes are simulated.")
        if state.get("pending"):
            review_form(controller, state["pending"])
        elif state["status"] == "running":
            st.info("The agent is working. This page updates automatically.")
        elif state["status"] == "complete":
            st.success("Review complete. Verified actions and anything needing follow-up are recorded below.")
        if state.get("error"):
            st.error(state["error"])
        action_results(state)
        if state.get("report"):
            st.download_button("Download JSON report", json.dumps(state["report"], indent=2),
                               file_name=f"{controller.id}_report.json", mime="application/json")
        with st.expander("Execution trace"):
            st.caption("Model calls, review decisions, and tool outcomes. Key values are redacted.")
            if state["events"]:
                st.json(state["events"])
            else:
                st.write("Waiting for the first pipeline event.")
        if state["status"] in ("running", "awaiting_review"):
            if st.button("Stop remaining actions", key="stop_run"):
                controller.cancel()
                st.info("Stopping before the next model call or approval. An in-flight operation may finish.")
        else:
            st.button("Set up another meeting", on_click=navigate, args=("New meeting",))
    live_panel()


def history_view():
    st.markdown('<div class="eyebrow">MEETING WORKSPACE / RUN HISTORY</div>', unsafe_allow_html=True)
    st.title("A record of every decision")
    st.write("Inspect saved UI runs and their outcomes. Historical reports are never rewritten by this view.")
    history = load_history()
    if not history:
        st.info("No UI runs yet. Your CLI reports remain in runs/; new UI runs will appear here.")
        return
    selected = st.selectbox("Saved run", history, format_func=lambda record: f"{record['title']} · {record['mode']} · {record['id']}")
    if selected["status"] in ("running", "awaiting_review") and (not active_controller() or active_controller().id != selected["id"]):
        st.warning("This snapshot may belong to a disconnected session or previous server process. It is read-only; no actions resume automatically.")
    metrics(selected)
    st.caption(f"Status: {selected['status']} · Started: {selected['started_at']} · Runtime: {selected.get('elapsed', 0)}s")
    action_results(selected)
    report_path = RUNS / selected["id"] / "report.json"
    if report_path.exists():
        st.download_button("Download saved report", report_path.read_text(), file_name=f"{selected['id']}.json", mime="application/json")
    with st.expander("Saved execution trace"):
        st.json(selected.get("events", []))


def evaluation_view():
    st.markdown('<div class="eyebrow">MEETING WORKSPACE / EVALUATION</div>', unsafe_allow_html=True)
    st.title("Compare the systems")
    st.write("Saved results for B0, B1, the full agent, and ablations. This page does not run experiments.")
    path = ROOT / "results/results.csv"
    if not path.exists():
        st.info("No saved evaluation table yet. Run the CLI evaluation after reviewing gold labels.")
        return
    with path.open() as file:
        rows = list(csv.DictReader(file))
    st.warning("These are historical pilot results from the repository, not scores from your live smoke tests or the current UI. Only reviewed gold supports accuracy scoring; the pilot's reviewed data is limited to test1.")
    systems = sorted({row.get("system", "") for row in rows})
    chosen = st.multiselect("Systems", systems, default=systems)
    filtered = [row for row in rows if row.get("system") in chosen]
    scores = defaultdict(list)
    for row in filtered:
        try:
            scores[row["system"]].append(float(row.get("f1", "")))
        except (ValueError, TypeError):
            pass
    if scores:
        st.subheader("Mean F1 on scored pilot rows")
        st.bar_chart([{"System": system, "F1": sum(values) / len(values)} for system, values in scores.items()],
                     x="System", y="F1", color="#12695e")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button("Download saved results CSV", path.read_bytes(), file_name="results.csv", mime="text/csv")
    with st.expander("How to run a new evaluation"):
        st.code("python -m eval.run_eval --split dev --systems b0,b1,a")
        st.caption("B1 and the agent use paid model requests. Review labels before interpreting accuracy. The UI does not change split assignments or promote draft gold.")


def connections_view():
    st.markdown('<div class="eyebrow">MEETING WORKSPACE / CONNECTIONS</div>', unsafe_allow_html=True)
    st.title("Your tools, your approval")
    st.write("Calendar, Trello, and Gmail run through your local Composio configuration. Keys stay on the server.")
    cols = st.columns(3)
    for col, title, detail in zip(cols, ["Google Calendar", "Trello", "Gmail"],
                                ["Create and read back events", "Assign and verify tasks", "Create and verify drafts only"]):
        with col.container(border=True):
            st.markdown(f"### {title}")
            st.write(detail)
    st.caption("Status is not checked automatically. This button lists connection metadata; it creates no account objects or external actions.")
    if mode == MODES[0]:
        st.info("Offline walkthrough needs no connected accounts. Select an OpenAI runtime and allow local configuration access to check your connections.")
        return
    if st.button("Check connections", type="primary", disabled=running()):
        try:
            config = read_local_config(st.session_state.get("allow_local_config", False))
            if not config.get("COMPOSIO_API_KEY"):
                raise ValueError("COMPOSIO_API_KEY is missing in local configuration.")
            from composio import Composio
            with st.spinner("Checking connection metadata…"):
                response = Composio(api_key=config["COMPOSIO_API_KEY"]).connected_accounts.list(
                    user_ids=[config.get("COMPOSIO_USER_ID") or "meeting-action-router"])
            st.session_state["connection_status"] = [{"Toolkit": item.toolkit.slug, "Status": item.status} for item in response.items]
            st.session_state["config_presence"] = {"OpenAI key present": bool(config.get("OPENAI_API_KEY")),
                "Trello destination configured": bool(config.get("TRELLO_LIST_ID"))}
        except (PermissionError, ValueError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Connection check failed ({type(exc).__name__}). No account actions were performed.")
    if "connection_status" in st.session_state:
        st.dataframe(st.session_state["connection_status"], hide_index=True, use_container_width=True)
        st.write(st.session_state["config_presence"])
        st.caption("Key presence is not OpenAI authentication or quota verification. Active connections do not prove every create/read-back operation will succeed.")


{"New meeting": new_meeting, "Current run": run_view, "Run history": history_view,
 "Evaluation": evaluation_view, "Connections": connections_view}[page]()
