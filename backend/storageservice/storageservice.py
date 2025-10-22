import sqlite3
import threading
from typing import Iterable, List, Optional, Sequence, Tuple, Union, Dict, Any

from ..schemas import (
    Flashcard,
    ExamQuestion,
    Project
)

Row = sqlite3.Row

SCHEMA_VERSION = 1


DDL = """
PRAGMA foreign_keys = ON;

-- 1) Users
CREATE TABLE IF NOT EXISTS users (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS users_update_ts
AFTER UPDATE ON users
BEGIN
  UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 2) Projects
CREATE TABLE IF NOT EXISTS projects (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  summary         TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, name)
);
CREATE TRIGGER IF NOT EXISTS projects_update_ts
AFTER UPDATE ON projects
BEGIN
  UPDATE projects SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 3) Documents
CREATE TABLE IF NOT EXISTS documents (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title           TEXT NOT NULL DEFAULT 'Untitled',
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(project_id, title)
);
CREATE TRIGGER IF NOT EXISTS documents_update_ts
AFTER UPDATE ON documents
BEGIN
  UPDATE documents SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 4) Document chunks
CREATE TABLE IF NOT EXISTS doc_chunks (
  id              INTEGER PRIMARY KEY,
  document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  seq             INTEGER NOT NULL,
  text            TEXT NOT NULL,
  embedding       BLOB,
  embedding_dim   INTEGER,
  embedding_model TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(document_id, seq)
);
CREATE TRIGGER IF NOT EXISTS doc_chunks_update_ts
AFTER UPDATE ON doc_chunks
BEGIN
  UPDATE doc_chunks SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 5) Flashcards
CREATE TABLE IF NOT EXISTS flashcards (
  id              INTEGER PRIMARY KEY,
  document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  front           TEXT NOT NULL,
  back            TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS flashcards_update_ts
AFTER UPDATE ON flashcards
BEGIN
  UPDATE flashcards SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 6) Exam questions
CREATE TABLE IF NOT EXISTS exam_questions (
  id              INTEGER PRIMARY KEY,
  document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  question        TEXT NOT NULL,
  option_a        TEXT NOT NULL,
  option_b        TEXT NOT NULL,
  option_c        TEXT NOT NULL,
  option_d        TEXT NOT NULL,
  answer_letter   TEXT NOT NULL CHECK (answer_letter IN ('A','B','C','D')),
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS exam_questions_update_ts
AFTER UPDATE ON exam_questions
BEGIN
  UPDATE exam_questions SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 7) Chat (one per project)
CREATE TABLE IF NOT EXISTS chats (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 8) Chat messages
CREATE TABLE IF NOT EXISTS chat_messages (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_projects_user      ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_docs_project       ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_docseq      ON doc_chunks(document_id, seq);
CREATE INDEX IF NOT EXISTS idx_cards_doc          ON flashcards(document_id);
CREATE INDEX IF NOT EXISTS idx_mcq_doc            ON exam_questions(document_id);
CREATE INDEX IF NOT EXISTS idx_chat_proj          ON chats(project_id);
CREATE INDEX IF NOT EXISTS idx_msg_chat_time      ON chat_messages(chat_id, created_at);

-- Views
CREATE VIEW IF NOT EXISTS v_project_overview AS
SELECT
  p.id            AS project_id,
  p.name          AS project_name,
  p.user_id,
  COUNT(DISTINCT d.id)                  AS document_count,
  COUNT(DISTINCT f.id)                  AS flashcard_count,
  COUNT(DISTINCT q.id)                  AS exam_question_count,
  MIN(d.created_at)                     AS first_doc_at,
  MAX(d.updated_at)                     AS last_doc_update_at
FROM projects p
LEFT JOIN documents d      ON d.project_id = p.id
LEFT JOIN flashcards f     ON f.document_id = d.id
LEFT JOIN exam_questions q ON q.document_id = d.id
GROUP BY p.id;

CREATE VIEW IF NOT EXISTS v_document_with_chunks AS
SELECT
  d.id            AS document_id,
  d.project_id,
  d.title,
  LENGTH(d.content)          AS content_len_chars,
  COUNT(c.id)                AS chunk_count,
  SUM(CASE WHEN c.embedding IS NOT NULL THEN 1 ELSE 0 END) AS chunk_with_emb_count
FROM documents d
LEFT JOIN doc_chunks c ON c.document_id = d.id
GROUP BY d.id;
"""

class StorageService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        # Initialize the schema using a temporary connection
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.row_factory = sqlite3.Row
        self._ensure_schema_with_connection(conn)
        conn.close()
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get a thread-local connection to the database."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.execute("PRAGMA foreign_keys = ON;")
            self._local.connection.execute("PRAGMA journal_mode = WAL;")
            self._local.connection.execute("PRAGMA synchronous = NORMAL;")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    # ---------- internal ----------
    def _ensure_schema_with_connection(self, conn: sqlite3.Connection) -> None:
        """Ensure schema exists using the provided connection."""
        cur = conn.execute("PRAGMA user_version;")
        version = cur.fetchone()[0]
        if version < 1:
            conn.executescript(DDL)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
            conn.commit()
        # Future migrations can go here (if version < 2: ...)

    def close(self) -> None:
        """Close the thread-local connection if it exists."""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            self._local.connection.commit()
            self._local.connection.close()
            self._local.connection = None

    def _one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Row]:
        cur = self.connection.execute(sql, params)
        return cur.fetchone()

    def _all(self, sql: str, params: Sequence[Any] = ()) -> List[Row]:
        cur = self.connection.execute(sql, params)
        return cur.fetchall()

    # ---------- users ----------
    def create_user(self, name: str) -> int:
        cur = self.connection.execute(
            "INSERT INTO users (name) VALUES (?)",
            (name,)
        )
        self.connection.commit()
        return cur.lastrowid

    def get_user_by_name(self, name: str) -> Optional[Row]:
        return self._one("SELECT * FROM users WHERE name = ?", (name,))

    def list_users(self) -> List[Row]:
        return self._all("SELECT * FROM users ORDER BY created_at ASC")

    def get_or_create_user(self, name: str) -> int:
        existing = self.get_user_by_name(name)
        if existing:
            return existing["id"]
        return self.create_user(name)

    # ---------- projects ----------
    def create_project(self, user_id: int, name: str, summary: Optional[str] = None) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO projects (user_id, name, summary) VALUES (?, ?, ?)",
                (user_id, name, summary)
            )
            pid = cur.lastrowid
            self.connection.execute("INSERT INTO chats (project_id) VALUES (?)", (pid,))
        return pid

    def update_project_summary(self, project_id: int, summary: Optional[str]) -> None:
        self.connection.execute(
            "UPDATE projects SET summary = ?, updated_at = datetime('now') WHERE id = ?",
            (summary, project_id)
        )
        self.connection.commit()

    def list_projects(self, user_id: int) -> List[Row]:
        return self._all(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY name",
            (user_id,)
        )

    def get_project_overview(self, project_id: int) -> Optional[Project]:
        row = self._one(
            "SELECT name, summary FROM projects WHERE id = ?",
            (project_id,)
        )

        if row:
            return Project(name=row["name"], summary=row["summary"] or "")
        return None

    def delete_project(self, project_id: int) -> None:
        self.connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.connection.commit()

    # ---------- documents ----------
    def create_document(self, project_id: int, title: str, content: str) -> int:
        cur = self.connection.execute(
            "INSERT INTO documents (project_id, title, content) VALUES (?, ?, ?)",
            (project_id, title, content)
        )
        self.connection.commit()
        return cur.lastrowid

    def update_document(self, document_id: int, *, title: Optional[str] = None, content: Optional[str] = None) -> None:
        if title is None and content is None:
            return
        if title is not None and content is not None:
            sql = "UPDATE documents SET title = ?, content = ?, updated_at = datetime('now') WHERE id = ?"
            params = (title, content, document_id)
        elif title is not None:
            sql = "UPDATE documents SET title = ?, updated_at = datetime('now') WHERE id = ?"
            params = (title, document_id)
        else:
            sql = "UPDATE documents SET content = ?, updated_at = datetime('now') WHERE id = ?"
            params = (content, document_id)
        self.connection.execute(sql, params)
        self.connection.commit()

    def get_document(self, document_id: int) -> Optional[Row]:
        return self._one("SELECT * FROM documents WHERE id = ?", (document_id,))

    def list_documents(self, project_id: int) -> List[Row]:
        rows = self._all(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,)
        )

        row_ids = [row["id"] for row in rows]
        return row_ids

    def list_documents_with_metadata(self, project_id: int) -> List[Row]:
        return self._all(
            "SELECT id, title, created_at, updated_at FROM documents WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,)
        )

    def list_documents_with_content(self, project_id: int) -> List[Row]:
        return self._all(
            "SELECT id, title, content, created_at, updated_at FROM documents WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,)
        )

    def delete_document(self, document_id: int) -> None:
        self.connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        self.connection.commit()

    # ---------- chunks & embeddings ----------
    def add_chunk(self, document_id: int, seq: int, text: str) -> int:
        cur = self.connection.execute(
            "INSERT INTO doc_chunks (document_id, seq, text) VALUES (?, ?, ?)",
            (document_id, seq, text)
        )
        self.connection.commit()
        return cur.lastrowid

    def bulk_add_chunks(self, document_id: int, chunks: Sequence[Tuple[int, str]]) -> None:
        """
        chunks: sequence of (seq, text)
        """
        self.connection.executemany(
            "INSERT INTO doc_chunks (document_id, seq, text) VALUES (?, ?, ?)",
            [(document_id, seq, text) for seq, text in chunks]
        )
        self.connection.commit()

    def set_chunk_embedding(
        self,
        chunk_id: int,
        embedding_bytes: Union[bytes, memoryview],
        embedding_dim: int,
        embedding_model: str
    ) -> None:
        self.connection.execute(
            """
            UPDATE doc_chunks
            SET embedding = ?, embedding_dim = ?, embedding_model = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (sqlite3.Binary(embedding_bytes), embedding_dim, embedding_model, chunk_id)
        )
        self.connection.commit()

    def list_chunks(self, document_id: int) -> List[Row]:
        return self._all(
            "SELECT * FROM doc_chunks WHERE document_id = ? ORDER BY seq ASC",
            (document_id,)
        )

    def fetch_project_chunk_embeddings(self, project_id: int) -> List[Tuple[int, bytes, Optional[int], Optional[str]]]:
        """
        Returns list of (chunk_id, embedding_bytes, embedding_dim, embedding_model) for all chunks in a project
        where embeddings are present.
        """
        sql = """
        SELECT c.id, c.embedding, c.embedding_dim, c.embedding_model
        FROM doc_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.project_id = ? AND c.embedding IS NOT NULL
        """
        cur = self.connection.execute(sql, (project_id,))
        return [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]

    def get_chunks_by_ids(self, chunk_ids: Sequence[int]) -> List[Row]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        sql = f"""
        SELECT c.id, c.document_id, c.seq, c.text, d.title
        FROM doc_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.id IN ({placeholders})
        """
        return self._all(sql, list(chunk_ids))

    # ---------- flashcards ----------
    def add_flashcard(self, document_id: int, front: str, back: str) -> int:
        cur = self.connection.execute(
            "INSERT INTO flashcards (document_id, front, back) VALUES (?, ?, ?)",
            (document_id, front, back)
        )
        self.connection.commit()
        return cur.lastrowid

    def list_flashcards(self, document_id: int) -> List[Row]:
        rows = self._all(
            "SELECT * FROM flashcards WHERE document_id = ? ORDER BY created_at ASC",
            (document_id,)
        )

        flashcards = [
            Flashcard(
                question=row["front"],
                answer=row["back"]
            ) for row in rows
        ]

        return flashcards

    def delete_flashcard(self, flashcard_id: int) -> None:
        self.connection.execute("DELETE FROM flashcards WHERE id = ?", (flashcard_id,))
        self.connection.commit()

    # ---------- exam questions ----------
    def add_exam_question(
        self,
        document_id: int,
        question: str,
        option_a: str,
        option_b: str,
        option_c: str,
        option_d: str,
        answer_letter: str
    ) -> int:
        cur = self.connection.execute(
            """
            INSERT INTO exam_questions
            (document_id, question, option_a, option_b, option_c, option_d, answer_letter)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (document_id, question, option_a, option_b, option_c, option_d, answer_letter)
        )
        self.connection.commit()
        return cur.lastrowid

    def list_exam_questions(self, document_id: int) -> List[Row]:
        rows = self._all(
            "SELECT * FROM exam_questions WHERE document_id = ? ORDER BY created_at ASC",
            (document_id,)
        )

        exam_questions = []
        for row in rows:
            options = [
                row["option_a"],
                row["option_b"],
                row["option_c"],
                row["option_d"],
            ]

            exam_questions.append(
                ExamQuestion(
                    question=row["question"],
                    options=options,
                    correctAnswer=row["answer_letter"].upper()
                )
            )

        return exam_questions

    def delete_exam_question(self, question_id: int) -> None:
        self.connection.execute("DELETE FROM exam_questions WHERE id = ?", (question_id,))
        self.connection.commit()

    # ---------- chat ----------
    def get_or_create_chat(self, project_id: int) -> int:
        row = self._one("SELECT id FROM chats WHERE project_id = ?", (project_id,))
        if row:
            return row["id"]
        cur = self.connection.execute("INSERT INTO chats (project_id) VALUES (?)", (project_id,))
        self.connection.commit()
        return cur.lastrowid

    def add_chat_message(self, project_id: int, role: str, content: str) -> int:
        chat_id = self.get_or_create_chat(project_id)
        cur = self.connection.execute(
            "INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        self.connection.commit()
        return cur.lastrowid

    def list_chat_messages(self, project_id: int, limit: Optional[int] = None) -> List[Row]:
        chat = self._one("SELECT id FROM chats WHERE project_id = ?", (project_id,))
        if not chat:
            return []
        if limit is None:
            sql = "SELECT * FROM chat_messages WHERE chat_id = ? ORDER BY created_at ASC, id ASC"
            return self._all(sql, (chat["id"],))
        else:
            sql = "SELECT * FROM chat_messages WHERE chat_id = ? ORDER BY created_at DESC, id DESC LIMIT ?"
            rows = self._all(sql, (chat["id"], limit))
            return list(reversed(rows))  # chronological

    # ---------- dashboards ----------
    def project_overview(self, user_id: int) -> List[Row]:
        return self._all(
            "SELECT * FROM v_project_overview WHERE user_id = ? ORDER BY project_name",
            (user_id,)
        )

    def document_stats(self, project_id: int) -> List[Row]:
        return self._all(
            "SELECT * FROM v_document_with_chunks WHERE project_id = ? ORDER BY title",
            (project_id,)
        )
    
_SERVICE: Optional[StorageService] = None
_SERVICE_LOCK = threading.Lock()

def get_database_service() -> StorageService:
    """Return a singleton StorageService instance.

    The instance is created lazily on first call and is protected by a
    module-level lock to be safe in multi-threaded contexts. The database
    path is relative to the package directory to keep behavior stable when
    called from different working directories.
    """
    global _SERVICE
    if _SERVICE is not None:
        return _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            # Use a path relative to this file so callers from other working
            # directories get the same database file.
            import os
            base = os.path.dirname(__file__)
            db_path = os.path.join(base, 'database.db')
            _SERVICE = StorageService(db_path)
    return _SERVICE
