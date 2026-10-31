from support_agent.config import Settings
from support_agent.database import connect, password_matches
from support_agent.models import Principal


def authenticate(settings: Settings, username: str, password: str) -> Principal | None:
    with connect(settings.database_path) as connection:
        user = connection.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if user is None or not password_matches(password, user["password_hash"]):
        return None
    return Principal(username=user["username"], role=user["role"], student_id=user["student_id"])

