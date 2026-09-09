from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProjectStore:
    """Transactional project records, with Firestore on Cloud Run and SQLite locally."""

    def __init__(self) -> None:
        self.backend = "sqlite"
        self._firestore = None
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        if project and os.getenv("K_SERVICE"):
            try:
                from google.cloud import firestore
                self._firestore = firestore.Client(project=project)
                self.backend = "firestore"
            except Exception:
                self._firestore = None
        self.path = Path(os.getenv("REEL_CREW_DB", "/tmp/reel-crew.db"))
        if not self._firestore:
            with sqlite3.connect(self.path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)")

    def save(self, project_id: str, payload: dict[str, Any], event: str = "project.saved") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        record = {**payload, "id": project_id, "updated_at": now, "storage": self.backend}
        audit = {"type": event, "project_id": project_id, "created_at": now}
        if self._firestore:
            batch = self._firestore.batch()
            batch.set(self._firestore.collection("reel_crew_projects").document(project_id), record)
            batch.set(self._firestore.collection("reel_crew_events").document(), audit)
            batch.commit()
        else:
            with sqlite3.connect(self.path) as db:
                db.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?)", (project_id, json.dumps(record), now))
                db.execute("INSERT INTO events(project_id,payload,created_at) VALUES (?, ?, ?)", (project_id, json.dumps(audit), now))
        return record

    def get(self, project_id: str) -> dict[str, Any] | None:
        if self._firestore:
            snap = self._firestore.collection("reel_crew_projects").document(project_id).get()
            return snap.to_dict() if snap.exists else None
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload FROM projects WHERE id=?", (project_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def events(self, project_id: str) -> list[dict[str, Any]]:
        if self._firestore:
            docs = self._firestore.collection("reel_crew_events").where("project_id", "==", project_id).stream()
            return sorted((d.to_dict() for d in docs), key=lambda x: x["created_at"], reverse=True)
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT payload FROM events WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

