from __future__ import annotations

import re
from pathlib import Path

from support_agent.database import audit, connect, now
from support_agent.models import Principal


class AuthorizationError(PermissionError):
    pass


class StudentService:
    def __init__(self, database_path: Path, principal: Principal) -> None:
        self.path = database_path
        self.principal = principal

    def my_fee_status(self) -> dict[str, str]:
        if self.principal.role != "student" or not self.principal.student_id:
            self._audit("read_fee_status", None, "denied", "role_required")
            raise AuthorizationError("Only a signed-in student can read a student fee status.")
        with connect(self.path) as connection:
            record = connection.execute("SELECT student_id,fee_status,scholarship_status FROM students WHERE student_id=?", (self.principal.student_id,)).fetchone()
        self._audit("read_fee_status", self.principal.student_id, "allowed", "returned")
        return dict(record)

    def request_email_change(self, new_email: str) -> dict[str, object]:
        if self.principal.role != "student" or not self.principal.student_id:
            self._audit("request_email_change", None, "denied", "role_required")
            raise AuthorizationError("Only a signed-in student can request a profile change.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", new_email.strip()):
            self._audit("request_email_change", self.principal.student_id, "denied", "invalid_value")
            raise ValueError("Enter a valid email address.")
        with connect(self.path) as connection:
            cursor = connection.execute("INSERT INTO approval_requests (student_id,field,new_value,status,requested_at) VALUES (?,?,?,?,?)", (self.principal.student_id, "email", new_email.strip(), "pending", now()))
            request_id = cursor.lastrowid
        self._audit("request_email_change", self.principal.student_id, "allowed", "pending", {"request_id": request_id, "field": "email"})
        return {"request_id": request_id, "status": "pending", "message": "Your email change is pending reviewer approval."}

    def my_requests(self) -> list[dict[str, object]]:
        if self.principal.role != "student" or not self.principal.student_id:
            raise AuthorizationError("Only a signed-in student can view their requests.")
        with connect(self.path) as connection:
            rows = connection.execute("SELECT request_id,field,status,requested_at,reviewed_at FROM approval_requests WHERE student_id=? ORDER BY request_id DESC", (self.principal.student_id,)).fetchall()
        self._audit("read_own_requests", self.principal.student_id, "allowed", "returned")
        return [dict(row) for row in rows]

    def pending_requests(self) -> list[dict[str, object]]:
        self._require_reviewer("read_pending_requests")
        with connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT
                    approval_requests.request_id,
                    approval_requests.student_id,
                    students.full_name AS requester_name,
                    approval_requests.field,
                    students.email AS current_value,
                    approval_requests.new_value,
                    approval_requests.status,
                    approval_requests.requested_at
                FROM approval_requests
                JOIN students ON students.student_id = approval_requests.student_id
                WHERE approval_requests.status = 'pending'
                ORDER BY approval_requests.request_id
                """
            ).fetchall()
        self._audit("read_pending_requests", None, "allowed", "returned")
        return [dict(row) for row in rows]

    def review(self, request_id: int, approve: bool) -> str:
        self._require_reviewer("review_email_change")
        with connect(self.path) as connection:
            request = connection.execute("SELECT * FROM approval_requests WHERE request_id=?", (request_id,)).fetchone()
            if request is None or request["status"] != "pending":
                self._audit("review_email_change", None, "denied", "not_pending", {"request_id": request_id})
                raise ValueError("That request is not pending.")
            if approve:
                connection.execute("UPDATE students SET email=? WHERE student_id=?", (request["new_value"], request["student_id"]))
                status, outcome = "approved", "executed"
            else:
                status, outcome = "rejected", "not_executed"
            connection.execute("UPDATE approval_requests SET status=?,reviewed_at=?,reviewer_username=? WHERE request_id=?", (status, now(), self.principal.username, request_id))
        self._audit("review_email_change", request["student_id"], "allowed", outcome, {"request_id": request_id})
        return outcome

    def _require_reviewer(self, action: str) -> None:
        if self.principal.role != "reviewer":
            self._audit(action, None, "denied", "reviewer_role_required")
            raise AuthorizationError("Reviewer authorization is required.")

    def _audit(self, action: str, subject_id: str | None, decision: str, outcome: str, metadata: dict[str, object] | None = None) -> None:
        audit(self.path, self.principal.username, action, subject_id, decision, outcome, metadata)

