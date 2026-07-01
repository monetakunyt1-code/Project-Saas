from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
REPORT_DIR = STORAGE_DIR / "reports"
HISTORY_DIR = STORAGE_DIR / "history"
TEMPLATE_DIR = STORAGE_DIR / "templates"

DATABASE_PATH = STORAGE_DIR / "docurapi.db"
LOG_FILE = BASE_DIR / "logs" / "docurapi.log"

MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSION = ".docx"

DIRECTORIES = (
    STORAGE_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    REPORT_DIR,
    HISTORY_DIR,
    TEMPLATE_DIR,
    LOG_FILE.parent,
)

for directory in DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)