# Assignment 2 — Safe Student Support Agent

A Groq-only Python and Streamlit project extending Assignment 1 with authenticated local identities, application-enforced authorization, reviewer approval, auditability, synthetic data, and privacy tests.

## Safety controls
- Three local identities authenticate using password hashes generated from local environment variables.
- A student service derives the target student ID from the authenticated principal, never from model tool arguments.
- Email changes create pending approval requests. Only the reviewer role can approve or reject; approval is the only code path that updates an email.
- SQLite audit events record actor, action, authorization decision, outcome, and safe metadata.
- All student data is fictional and the local database is excluded from Git.

## Setup
Copy .env.example to .env and set all five values. Do not commit .env.

Create a virtual environment and install dependencies:

    py -3.14 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Run tests:

    .\.venv\Scripts\python.exe -m pytest

Launch the app:

    .\.venv\Scripts\python.exe -m streamlit run app.py

Sign in with student1, student2, or reviewer and the corresponding local password you configured in .env.

### Windows install note

This project pins Streamlit 1.41.1 because newer Streamlit releases include deeply nested template files that can exceed Windows path limits in the Codex workspace path. If a previous installation failed, delete `.venv`, recreate it, and rerun the install commands above.

## Architecture
The Streamlit session contains only the authenticated principal. StudentService checks role and ownership before each database operation. The Groq agent receives tool schemas but no authority: local tool implementations enforce all controls. Audit events are written for allowed and denied operations.

## Evaluation
tests/test_security.py verifies own-record access, pending approval, rejection without execution, and reviewer restrictions. Add the test output and Streamlit workflows to the Assignment 2 video evidence.

