"""Professional Streamlit interface for the Assignment 2 support agent."""

from __future__ import annotations

from html import escape

import streamlit as st

from support_agent.agent import run_agent
from support_agent.auth import authenticate
from support_agent.config import ConfigurationError, load_settings
from support_agent.database import initialize
from support_agent.service import StudentService


st.set_page_config(
    page_title="Student Support Hub",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp {background: radial-gradient(circle at 92% 4%, #d9f7f2 0, transparent 26%),
              radial-gradient(circle at 8% 30%, #e6eeff 0, transparent 21%), #f6f8fc;}
      .block-container {max-width: 1200px; padding-top: 1.7rem; padding-bottom: 3rem;}
      section[data-testid="stSidebar"] {background: linear-gradient(170deg, #101b4d, #173c6a 55%, #087d78);}
      section[data-testid="stSidebar"] * {color: #f4fbff !important;}
      section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #b9d7e7 !important;}
      .hero {position:relative; overflow:hidden; padding:2.2rem 2.5rem; border-radius:26px; color:white;
             background:linear-gradient(125deg,#101b4d 0%,#2457a7 52%,#00a58f 100%);
             box-shadow:0 20px 42px rgba(29,60,125,.24); margin-bottom:1.55rem;}
      .hero:after {content:""; position:absolute; right:-90px; top:-120px; width:310px; height:310px;
                    border:1px solid rgba(255,255,255,.24); border-radius:50%;
                    box-shadow:0 0 0 32px rgba(255,255,255,.06),0 0 0 74px rgba(255,255,255,.04);}
      .kicker {color:#aef7e6; font-size:.74rem; font-weight:800; letter-spacing:.15em; text-transform:uppercase;}
      .hero h1 {font-size:2.45rem; letter-spacing:-.05em; margin:.4rem 0 .45rem; color:white;}
      .hero p {max-width:720px; margin:0; color:#dcecff; font-size:1.03rem;}
      .glass-card {background:rgba(255,255,255,.94); border:1px solid #dce6f3; border-radius:18px;
                   padding:1.15rem 1.25rem; min-height:118px; box-shadow:0 8px 22px rgba(25,50,86,.07);}
      .glass-card .icon {font-size:1.35rem;} .glass-card b {display:block;color:#132953;margin:.35rem 0 .16rem;}
      .glass-card span {color:#5d6e85;font-size:.9rem;line-height:1.4;}
      .eyebrow {margin:1.7rem 0 .5rem; color:#19726f; font-size:.76rem; font-weight:800; letter-spacing:.13em;text-transform:uppercase;}
      .account-card {background:linear-gradient(135deg,#ffffff,#f3fcfb); border:1px solid #c9ebe4; border-radius:20px;
                     padding:1.35rem 1.5rem; margin:.3rem 0 1rem;}
      .account-card h3 {margin:0 0 .25rem;color:#132953}.account-card p{margin:0;color:#5d6e85}
      .request-card {background:white; border:1px solid #dce6f3; border-radius:19px; padding:1.15rem 1.25rem;
                     box-shadow:0 8px 20px rgba(25,50,86,.06); margin-bottom:1rem;}
      .change-box {border-radius:14px;padding:.8rem 1rem;min-height:86px}.before{background:#edf3fb;color:#284466}.after{background:#fff4df;color:#805500}
      .badge {display:inline-block;padding:.28rem .68rem;border-radius:999px;background:#e5f8f2;color:#087466;font-weight:750;font-size:.78rem;}
      div[data-testid="stMetric"] {background:#fff;border:1px solid #dce6f3;border-radius:15px;padding:.8rem;box-shadow:0 5px 14px rgba(25,50,86,.05);}
      div.stButton > button {border-radius:11px;font-weight:700;min-height:2.55rem;border:1px solid #cbd9e9;}
      div.stButton > button[kind="primary"] {background:linear-gradient(105deg,#1767c1,#0a9887);border:0;}
      div[data-testid="stForm"] {border:1px solid #dce6f3;border-radius:20px;background:rgba(255,255,255,.92);padding:1.2rem 1.35rem;box-shadow:0 10px 24px rgba(25,50,86,.07);}
      [data-testid="stTabs"] button {font-weight:700;}
    </style>
    """,
    unsafe_allow_html=True,
)


def safe(value: object) -> str:
    return escape(str(value))


def display_name(principal) -> str:
    return {"student1": "Asha Sharma", "student2": "Rahul Mehta", "reviewer": "Student Services Reviewer"}.get(principal.username, principal.username)


try:
    settings = load_settings()
    initialize(settings)
except ConfigurationError as error:
    st.error(str(error))
    st.stop()

if "principal" not in st.session_state:
    st.session_state.principal = None
if "agent_result" not in st.session_state:
    st.session_state.agent_result = None

st.markdown(
    """
    <section class="hero">
      <div class="kicker">Secure student services · assignment 2</div>
      <h1>Student Support Hub</h1>
      <p>Private account help with verified identity, application-enforced access controls, human approval for sensitive changes, and a complete audit trail.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.principal:
    intro_one, intro_two, intro_three = st.columns(3)
    for column, icon, title, copy in (
        (intro_one, "🔐", "Verified sign-in", "Local credentials establish a role before private data is available."),
        (intro_two, "🛡️", "Enforced access", "Student ownership is checked by application code, not by the AI model."),
        (intro_three, "✅", "Human approval", "Sensitive email changes remain pending until a reviewer decides."),
    ):
        with column:
            st.markdown(f"<div class='glass-card'><div class='icon'>{icon}</div><b>{title}</b><span>{copy}</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='eyebrow'>Secure sign-in</div>", unsafe_allow_html=True)
    left, right = st.columns([1.1, .9])
    with left:
        with st.form("login"):
            st.subheader("Access your workspace")
            username = st.selectbox("Account", ["student1", "student2", "reviewer"])
            password = st.text_input("Local password", type="password")
            if st.form_submit_button("Sign in securely", type="primary", use_container_width=True):
                principal = authenticate(settings, username, password)
                if principal:
                    st.session_state.principal = principal
                    st.rerun()
                st.error("Sign-in failed. Check the local password in your .env file.")
    with right:
        st.markdown("<div class='account-card'><h3>Demo environment</h3><p>All records are fictional and exist solely for this academic project. Passwords remain local and are never committed to Git.</p></div>", unsafe_allow_html=True)
        st.info("Choose a role, enter its local password, then explore its permitted workflow.")
    st.stop()

principal = st.session_state.principal
service = StudentService(settings.database_path, principal)
with st.sidebar:
    st.markdown("## 🛡️ Support Hub")
    st.caption("Production-aware student services")
    st.divider()
    st.markdown("### Signed in")
    st.success(display_name(principal))
    st.caption("Role: " + principal.role.title())
    st.divider()
    st.markdown("### Safety controls")
    st.write("✓ Role-aware access\n\n✓ Ownership checks\n\n✓ Approval gate\n\n✓ Audit trail")
    if st.button("Sign out", use_container_width=True):
        st.session_state.principal = None
        st.session_state.agent_result = None
        st.rerun()

if principal.role == "reviewer":
    st.markdown("<div class='eyebrow'>Reviewer workspace</div>", unsafe_allow_html=True)
    st.title("Approval control center")
    pending_requests = service.pending_requests()
    first, second, third = st.columns(3)
    first.metric("Pending reviews", len(pending_requests))
    second.metric("Execution rule", "Approval required")
    third.metric("Audit coverage", "Enabled")
    st.caption("Every review decision is persisted with the reviewer identity and execution outcome.")
    if not pending_requests:
        st.success("Your queue is clear. There are no pending changes requiring review.")
    for request in pending_requests:
        st.markdown("<div class='request-card'>", unsafe_allow_html=True)
        top, badge = st.columns([5, 1])
        top.markdown("#### " + safe(request["requester_name"]) + " · `" + safe(request["student_id"]) + "`")
        badge.markdown("<span class='badge'>PENDING</span>", unsafe_allow_html=True)
        st.caption("Request #" + str(request["request_id"]) + " · Submitted " + safe(request["requested_at"]))
        st.markdown("**Email change request**")
        before, arrow, after = st.columns([5, 1, 5])
        before.markdown("<div class='change-box before'><b>Current email</b><br>" + safe(request["current_value"]) + "</div>", unsafe_allow_html=True)
        arrow.markdown("<h2 style='text-align:center;padding-top:18px;color:#207c87'>→</h2>", unsafe_allow_html=True)
        after.markdown("<div class='change-box after'><b>Requested email</b><br>" + safe(request["new_value"]) + "</div>", unsafe_allow_html=True)
        st.caption("Approve applies this change to the synthetic record. Reject preserves the current email unchanged.")
        approve, reject = st.columns(2)
        if approve.button("Approve and apply", key="a" + str(request["request_id"]), type="primary", use_container_width=True):
            service.review(request["request_id"], True)
            st.success("Request approved and email update executed.")
            st.rerun()
        if reject.button("Reject and keep current email", key="r" + str(request["request_id"]), use_container_width=True):
            service.review(request["request_id"], False)
            st.warning("Request rejected. No student record was changed.")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='eyebrow'>Student workspace</div>", unsafe_allow_html=True)
    st.markdown("<div class='account-card'><h3>Welcome back, " + safe(display_name(principal)) + "</h3><p>Your workspace is restricted to your authenticated student account. Private data from other students is not available.</p></div>", unsafe_allow_html=True)
    overview, assistant, changes = st.tabs(["📊 My account", "✨ Ask the agent", "📝 Change requests"])
    with overview:
        st.subheader("Your account snapshot")
        if st.button("Load my fee and scholarship status", type="primary"):
            st.session_state.account = service.my_fee_status()
        account = st.session_state.get("account")
        if account:
            fee, scholarship, protection = st.columns(3)
            fee.metric("Fee status", account["fee_status"])
            scholarship.metric("Scholarship", account["scholarship_status"])
            protection.metric("Access scope", "My account only")
        else:
            st.info("Load your snapshot to view your private synthetic account information.")
    with assistant:
        st.subheader("Groq support assistant")
        st.caption("The assistant uses local tools for account actions; it cannot override ownership or approval controls.")
        question = st.text_area("What do you need help with?", placeholder="For example: What is my fee status?", max_chars=2000)
        if st.button("Ask safely", type="primary") and question.strip():
            try:
                with st.spinner("Checking your permitted information..."):
                    st.session_state.agent_result = run_agent(settings, principal, question)
            except Exception as error:
                st.error("Agent request failed: " + type(error).__name__)
        result = st.session_state.agent_result
        if result:
            st.success(result.answer)
            a, b, c = st.columns(3)
            a.metric("Latency", str(result.latency_ms) + " ms")
            b.metric("Tokens", str((result.prompt_tokens or 0) + (result.completion_tokens or 0)))
            c.metric("Tools used", len(result.tools))
            if result.tools:
                st.caption("Tool activity: " + " · ".join(result.tools))
    with changes:
        st.subheader("Request an email update")
        st.caption("Email changes are sensitive actions. They will remain pending until a reviewer approves or rejects them.")
        with st.form("email_change"):
            email = st.text_input("New email address")
            submitted = st.form_submit_button("Submit for reviewer approval", type="primary")
            if submitted:
                try:
                    result = service.request_email_change(email)
                    st.success(result["message"] + " Request #" + str(result["request_id"]) + ".")
                except ValueError as error:
                    st.error(str(error))
        st.markdown("#### My request history")
        st.dataframe(service.my_requests(), use_container_width=True, hide_index=True)
