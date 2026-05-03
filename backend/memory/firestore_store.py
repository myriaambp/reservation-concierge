"""Persistent memory: user prefs, watches, snapshots, notifications, bookings.

Backed by Firestore in production; transparently falls back to an in-process
JSON file when no GCP project is configured (local dev mode). The interface is
the same so agent code never branches on backend.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.memory.state import UserPrefs, Watch

# Lazy import: google-cloud-firestore is heavy; only load if we'll use it.
_firestore_client = None
_lock = threading.Lock()

_LOCAL_STORE_PATH = Path(__file__).resolve().parents[2] / ".local_store.json"


def _firestore() -> Any | None:
    """Return a Firestore client if configured + available, else None."""
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    settings = get_settings()
    if not settings.gcp_project_id and not os.getenv("FIRESTORE_EMULATOR_HOST"):
        return None

    with _lock:
        if _firestore_client is None:
            try:
                from google.cloud import firestore  # type: ignore
                _firestore_client = firestore.Client(
                    project=settings.gcp_project_id or None
                )
            except Exception:
                _firestore_client = None
    return _firestore_client


class MemoryStore:
    """Single class, two backends. If Firestore is configured, use it.
    Otherwise, persist to a local JSON file so dev workflow is friction-free.
    """

    # ---------- backend dispatch ----------
    def _local_load(self) -> dict:
        if not _LOCAL_STORE_PATH.exists():
            return {
                "users": {},
                "watches": {},
                "snapshots": {},
                "bookings": {},
                "notifications": [],
            }
        return json.loads(_LOCAL_STORE_PATH.read_text() or "{}")

    def _local_save(self, data: dict) -> None:
        _LOCAL_STORE_PATH.write_text(json.dumps(data, indent=2, default=str))

    # ---------- USERS ----------
    def get_user(self, user_id: str) -> UserPrefs:
        fs = _firestore()
        if fs is not None:
            doc = fs.collection("users").document(user_id).get()
            if doc.exists:
                return UserPrefs(**doc.to_dict())
            return UserPrefs(user_id=user_id)

        data = self._local_load()
        rec = data["users"].get(user_id)
        return UserPrefs(**rec) if rec else UserPrefs(user_id=user_id)

    def upsert_user(self, prefs: UserPrefs) -> None:
        fs = _firestore()
        if fs is not None:
            fs.collection("users").document(prefs.user_id).set(
                prefs.model_dump()
            )
            return
        data = self._local_load()
        data["users"][prefs.user_id] = prefs.model_dump()
        self._local_save(data)

    # ---------- WATCHES ----------
    def add_watch(self, watch: Watch) -> None:
        fs = _firestore()
        if fs is not None:
            fs.collection("watches").document(watch.id).set(watch.model_dump())
            return
        data = self._local_load()
        data["watches"][watch.id] = watch.model_dump()
        self._local_save(data)

    def list_watches(self, user_id: str | None = None, active_only: bool = True) -> list[Watch]:
        fs = _firestore()
        if fs is not None:
            q = fs.collection("watches")
            if user_id:
                q = q.where("user_id", "==", user_id)
            if active_only:
                q = q.where("active", "==", True)
            return [Watch(**doc.to_dict()) for doc in q.stream()]

        data = self._local_load()
        out = []
        for w in data["watches"].values():
            if user_id and w["user_id"] != user_id:
                continue
            if active_only and not w["active"]:
                continue
            out.append(Watch(**w))
        return out

    def cancel_watch(self, watch_id: str) -> None:
        fs = _firestore()
        if fs is not None:
            fs.collection("watches").document(watch_id).update(
                {"active": False}
            )
            return
        data = self._local_load()
        if watch_id in data["watches"]:
            data["watches"][watch_id]["active"] = False
            self._local_save(data)

    # ---------- SNAPSHOTS (for hash-diff polling) ----------
    def get_snapshot(self, restaurant_id: str) -> str | None:
        fs = _firestore()
        if fs is not None:
            doc = fs.collection("snapshots").document(restaurant_id).get()
            if doc.exists:
                return doc.to_dict().get("hash")
            return None
        data = self._local_load()
        return data["snapshots"].get(restaurant_id)

    def set_snapshot(self, restaurant_id: str, snapshot_hash: str) -> None:
        fs = _firestore()
        if fs is not None:
            fs.collection("snapshots").document(restaurant_id).set(
                {"hash": snapshot_hash}
            )
            return
        data = self._local_load()
        data["snapshots"][restaurant_id] = snapshot_hash
        self._local_save(data)

    # ---------- BOOKINGS ----------
    def record_booking(self, booking: dict) -> None:
        fs = _firestore()
        if fs is not None:
            fs.collection("bookings").document(booking["id"]).set(booking)
            return
        data = self._local_load()
        data["bookings"][booking["id"]] = booking
        self._local_save(data)

    # ---------- NOTIFICATIONS ----------
    def record_notification(self, payload: dict) -> None:
        fs = _firestore()
        if fs is not None:
            fs.collection("notifications").add(payload)
            return
        data = self._local_load()
        data["notifications"].append(payload)
        self._local_save(data)

    def recent_notifications(self, user_id: str, limit: int = 10) -> list[dict]:
        fs = _firestore()
        if fs is not None:
            q = (
                fs.collection("notifications")
                .where("user_id", "==", user_id)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
            )
            return [doc.to_dict() for doc in q.stream()]
        data = self._local_load()
        notes = [n for n in data["notifications"] if n.get("user_id") == user_id]
        notes.sort(key=lambda n: n.get("created_at", ""), reverse=True)
        return notes[:limit]


_store_singleton: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = MemoryStore()
    return _store_singleton
