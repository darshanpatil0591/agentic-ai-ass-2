from pathlib import Path
from support_agent.config import Settings
from support_agent.database import initialize
from support_agent.models import Principal
from support_agent.service import AuthorizationError, StudentService

def settings(path):
    return Settings("key","model","one","two","review",path,Path("."))

def test_ownership_and_approval():
    database=Path(__file__).parent / ".test-runtime.sqlite"
    database.unlink(missing_ok=True)
    try:
        initialize(settings(database))
        student=StudentService(database,Principal("student1","student","S1001"))
        assert student.my_fee_status()["student_id"]=="S1001"
        request=student.request_email_change("new@example.test")
        assert student.my_requests()[0]["status"]=="pending"
        reviewer=StudentService(database,Principal("reviewer","reviewer"))
        pending=reviewer.pending_requests()[0]
        assert pending["requester_name"]=="Asha Sharma"
        assert pending["current_value"]=="asha@example.test"
        assert pending["new_value"]=="new@example.test"
        assert reviewer.review(request["request_id"],False)=="not_executed"
        try: reviewer.my_fee_status()
        except AuthorizationError: pass
        else: assert False
    finally:
        database.unlink(missing_ok=True)

