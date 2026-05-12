import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

MGO_NAME = "Elan"

MODEL_NOTE  = "claude-haiku-4-5-20251001"
MODEL_EMAIL = "claude-opus-4-7"
MODEL_JUDGE = "claude-opus-4-7"

ROOT          = Path(__file__).resolve().parent.parent
SKILL_DIR     = ROOT / "skills" / "email-voice"
PROMPTS_DIR   = ROOT / "prompts"
SCHEMAS_DIR   = ROOT / "schemas"
DATA_DIR      = ROOT / "data"
ACTIVITY_LOG  = DATA_DIR / "activity_log.json"
TEST_CASES    = DATA_DIR / "test_cases.json"
