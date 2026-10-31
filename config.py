from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    student_one_password: str
    student_two_password: str
    reviewer_password: str
    database_path: Path
    project_root: Path


def load_settings() -> Settings:
    load_dotenv(override=False)
    root = Path(__file__).resolve().parents[1]
    required = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", "").strip(),
        "STUDENT_ONE_PASSWORD": os.getenv("STUDENT_ONE_PASSWORD", "").strip(),
        "STUDENT_TWO_PASSWORD": os.getenv("STUDENT_TWO_PASSWORD", "").strip(),
        "REVIEWER_PASSWORD": os.getenv("REVIEWER_PASSWORD", "").strip(),
    }
    missing = [name for name, value in required.items() if not value or value.startswith("choose_") or value.startswith("replace_")]
    if missing:
        raise ConfigurationError("Set these local values in .env: " + ", ".join(missing))
    return Settings(
        groq_api_key=required["GROQ_API_KEY"],
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(),
        student_one_password=required["STUDENT_ONE_PASSWORD"],
        student_two_password=required["STUDENT_TWO_PASSWORD"],
        reviewer_password=required["REVIEWER_PASSWORD"],
        database_path=root / "data" / "runtime" / "student_support.db",
        project_root=root,
    )

