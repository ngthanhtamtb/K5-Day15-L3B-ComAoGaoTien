from pathlib import Path
from app.core.config import settings


for dir_path in settings.UPLOAD_DIRS:
    Path(dir_path).mkdir(parents=True, exist_ok=True)
