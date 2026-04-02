import glob
import os
import re
import zipfile
from dataclasses import dataclass

from src.config.config_loader import CONFIG


DEFAULT_INBOX_ROOT = os.path.join(os.path.expanduser("~"), "Desktop", "hana_inbox")


@dataclass
class InboxSelection:
    category: str
    path: str


class InboxManager:
    """Resolve arquivos da Hana Inbox por categoria e rastreia o arquivo ativo."""

    CATEGORY_DIRS = {
        "imagem": "imagem",
        "image": "imagem",
        "pdf": "pdf",
        "docs": "docs",
        "doc": "docs",
        "documento": "docs",
        "documentos": "docs",
        "code": "code",
        "codigo": "code",
        "código": "code",
        "audio": "audio",
        "áudio": "audio",
        "video": "video",
        "vídeo": "video",
    }

    CATEGORY_EXTENSIONS = {
        "imagem": {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"},
        "pdf": {".pdf"},
        "docs": {".txt", ".md", ".json", ".csv", ".xml", ".yaml", ".yml", ".log", ".docx"},
        "code": {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".json",
            ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".rs", ".go", ".php", ".rb",
            ".sql", ".sh", ".ps1", ".bat", ".toml", ".ini", ".env", ".yaml", ".yml",
        },
        "audio": {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"},
        "video": {".mp4", ".avi", ".mov", ".webm", ".mkv", ".m4v"},
    }

    def __init__(self):
        configured = CONFIG.get("HANA_INBOX_ROOT", "")
        self.root_dir = configured if configured else DEFAULT_INBOX_ROOT
        self.active_files: dict[str, str] = {}
        self.last_active: InboxSelection | None = None
        # Auto-cria a pasta inbox na primeira execução
        os.makedirs(self.root_dir, exist_ok=True)

    def normalize_category(self, category: str) -> str:
        key = (category or "").strip().lower()
        return self.CATEGORY_DIRS.get(key, key)

    def get_category_dir(self, category: str) -> str:
        normalized = self.normalize_category(category)
        folder_name = self.CATEGORY_DIRS.get(normalized, normalized)
        return os.path.join(self.root_dir, folder_name)

    def get_latest_file(self, category: str) -> str | None:
        normalized = self.normalize_category(category)
        category_dir = self.get_category_dir(normalized)
        allowed_exts = self.CATEGORY_EXTENSIONS.get(normalized, set())
        if not os.path.isdir(category_dir):
            return None

        files = []
        for name in os.listdir(category_dir):
            path = os.path.join(category_dir, name)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if allowed_exts and ext not in allowed_exts:
                continue
            files.append(path)

        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def set_active_file(self, category: str, path: str):
        normalized = self.normalize_category(category)
        self.active_files[normalized] = path
        self.last_active = InboxSelection(category=normalized, path=path)

    def get_active_file(self, category: str | None = None) -> str | None:
        if category:
            normalized = self.normalize_category(category)
            path = self.active_files.get(normalized)
            if path and os.path.exists(path):
                return path
            return None
        if self.last_active and os.path.exists(self.last_active.path):
            return self.last_active.path
        return None

    def select_latest(self, category: str) -> str | None:
        path = self.get_latest_file(category)
        if path:
            self.set_active_file(category, path)
        return path

    def describe_selection(self, category: str, path: str) -> str:
        normalized = self.normalize_category(category)
        return f"Arquivo ativo da inbox ({normalized}): {os.path.basename(path)} | Path: {path}"

    def read_text_like(self, path: str, max_chars: int = 120000) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".docx":
            return self._read_docx(path, max_chars=max_chars)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars + 1)
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...[TRUNCADO]..."
        return content

    def read_pdf(self, path: str, max_chars: int = 120000) -> str:
        reader = None
        errors = []

        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
        except Exception as e:
            errors.append(str(e))

        if reader is None:
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(path)
            except Exception as e:
                errors.append(str(e))

        if reader is None:
            raise RuntimeError(
                "Não encontrei biblioteca de PDF compatível (pypdf/PyPDF2). "
                f"Detalhes: {' | '.join(errors)}"
            )

        chunks = []
        total_chars = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            if not text.strip():
                continue
            remaining = max_chars - total_chars
            if remaining <= 0:
                break
            text = text[:remaining]
            chunks.append(text)
            total_chars += len(text)

        content = "\n\n".join(chunks).strip()
        if not content:
            raise RuntimeError("Não consegui extrair texto útil do PDF.")
        if total_chars >= max_chars:
            content += "\n\n...[TRUNCADO]..."
        return content

    def build_context_block(self, category: str, path: str, content: str) -> str:
        normalized = self.normalize_category(category)
        return (
            f"--- INBOX {normalized.upper()} ({os.path.basename(path)}) ---\n"
            f"PATH: {path}\n"
            f"{content}\n"
            f"--- FIM INBOX {normalized.upper()} ---"
        )

    def find_by_name(self, category: str, spoken_name: str) -> str | None:
        normalized = self.normalize_category(category)
        category_dir = self.get_category_dir(normalized)
        if not os.path.isdir(category_dir):
            return None

        tokens = [t for t in re.split(r"[\s_\-\.]+", spoken_name.lower()) if t]
        if not tokens:
            return None

        best = None
        best_score = 0
        for path in glob.glob(os.path.join(category_dir, "*")):
            if not os.path.isfile(path):
                continue
            filename = os.path.basename(path).lower()
            score = sum(1 for token in tokens if token in filename)
            if score > best_score:
                best = path
                best_score = score

        if best and best_score > 0:
            self.set_active_file(normalized, best)
            return best
        return None

    def _read_docx(self, path: str, max_chars: int = 120000) -> str:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
        text = re.sub(r"</w:p>", "\n", xml)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n...[TRUNCADO]..."
        return text
