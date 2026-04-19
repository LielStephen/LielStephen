"""
face_auth.py — Core face authentication logic.

Handles:
  - Registering a new user face (encoding + persisting to disk)
  - Authenticating an image against registered faces
  - Listing / deleting registered users
"""

import re
import json
import logging
from pathlib import Path

import numpy as np
import face_recognition

logger = logging.getLogger(__name__)

# Default directory that stores per-user face encoding files
_DEFAULT_DB = Path(__file__).parent / "known_faces"

# Cosine / L2-distance threshold — faces within this distance are considered a match
_DEFAULT_TOLERANCE = 0.50


class FaceAuthenticator:
    """Manages face registration and authentication."""

    def __init__(self, db_dir: str | Path = _DEFAULT_DB, tolerance: float = _DEFAULT_TOLERANCE):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.tolerance = tolerance
        self._cache: dict[str, list[np.ndarray]] = {}  # username -> list of encodings

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _user_file(self, username: str) -> Path:
        return self.db_dir / f"{username}.json"

    def _load_user(self, username: str) -> list[np.ndarray]:
        """Return cached or disk-loaded encodings for *username*."""
        if username in self._cache:
            return self._cache[username]
        path = self._user_file(username)
        if not path.exists():
            return []
        with path.open() as f:
            data = json.load(f)
        encodings = [np.array(enc) for enc in data["encodings"]]
        self._cache[username] = encodings
        return encodings

    def _save_user(self, username: str, encodings: list[np.ndarray]) -> None:
        path = self._user_file(username)
        with path.open("w") as f:
            json.dump({"username": username, "encodings": [enc.tolist() for enc in encodings]}, f)
        self._cache[username] = encodings

    @staticmethod
    def _get_encodings(image_path: str | Path) -> list[np.ndarray]:
        """Load *image_path* and return all detected face encodings."""
        image = face_recognition.load_image_file(str(image_path))
        locations = face_recognition.face_locations(image, model="hog")
        encodings = face_recognition.face_encodings(image, locations)
        return encodings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_username(username: str) -> str:
        """
        Strip whitespace and reject usernames that could cause path traversal.
        Allowed characters: alphanumerics, hyphens, underscores, and dots
        (but not leading dots or sequences that traverse directories).
        """
        username = username.strip()
        if not username or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", username):
            raise ValueError(
                "Invalid username. Use only letters, digits, hyphens, underscores, and dots (max 64 chars)."
            )
        if username.startswith(".") or ".." in username:
            raise ValueError("Invalid username: must not start with a dot or contain '..'.")
        return username

    def register(self, username: str, image_path: str | Path) -> dict:
        """
        Register a face for *username* from the given image.

        Returns a result dict:
          {"success": True,  "message": "...", "face_count": N}
          {"success": False, "message": "..."}
        """
        try:
            username = self._validate_username(username)
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

        encodings = self._get_encodings(image_path)
        if not encodings:
            return {"success": False, "message": "No face detected in the provided image."}
        if len(encodings) > 1:
            return {
                "success": False,
                "message": f"Multiple faces detected ({len(encodings)}). Please provide an image with exactly one face.",
            }

        existing = self._load_user(username)
        # Check for duplicates within this user's own encodings
        matches = face_recognition.compare_faces(existing, encodings[0], tolerance=self.tolerance)
        if any(matches):
            return {"success": False, "message": "This face is already registered for that user."}

        existing.append(encodings[0])
        self._save_user(username, existing)
        logger.info("Registered face for '%s' (total encodings: %d)", username, len(existing))
        return {
            "success": True,
            "message": f"Face registered successfully for '{username}'.",
            "face_count": len(existing),
        }

    def authenticate(self, image_path: str | Path) -> dict:
        """
        Authenticate a face against all registered users.

        Returns:
          {"authenticated": True,  "username": "...", "confidence": 0.92}
          {"authenticated": False, "message": "..."}
        """
        encodings = self._get_encodings(image_path)
        if not encodings:
            return {"authenticated": False, "message": "No face detected in the provided image."}
        if len(encodings) > 1:
            return {
                "authenticated": False,
                "message": f"Multiple faces detected ({len(encodings)}). Please use an image with a single face.",
            }

        probe = encodings[0]
        best_match: str | None = None
        best_distance = float("inf")

        for user_file in self.db_dir.glob("*.json"):
            username = user_file.stem
            known = self._load_user(username)
            if not known:
                continue
            distances = face_recognition.face_distance(known, probe)
            min_dist = float(np.min(distances))
            if min_dist < self.tolerance and min_dist < best_distance:
                best_distance = min_dist
                best_match = username

        if best_match:
            confidence = round(1.0 - best_distance, 4)
            logger.info("Authenticated as '%s' (confidence %.2f)", best_match, confidence)
            return {"authenticated": True, "username": best_match, "confidence": confidence}

        return {"authenticated": False, "message": "Face not recognized. Access denied."}

    def list_users(self) -> list[str]:
        """Return a sorted list of registered usernames."""
        return sorted(p.stem for p in self.db_dir.glob("*.json"))

    def delete_user(self, username: str) -> bool:
        """Delete all face data for *username*. Returns True if the user existed."""
        try:
            username = self._validate_username(username)
        except ValueError:
            return False
        path = self._user_file(username)
        if path.exists():
            path.unlink()
            self._cache.pop(username, None)
            logger.info("Deleted user '%s'", username)
            return True
        return False
