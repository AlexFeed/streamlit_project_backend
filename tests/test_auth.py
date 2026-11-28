import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_routes import router as auth_router
from app.services import auth_service


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_file = Path(self.temp_dir.name) / "users.json"
        self.users_patch = patch.object(
            auth_service,
            "USERS_FILE",
            self.users_file,
        )
        self.users_patch.start()
        self.addCleanup(self.users_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

        app = FastAPI()
        app.include_router(auth_router)
        self.client = TestClient(app)

    def _register(
        self,
        email: str = "alice@example.com",
        password: str = "secret123",
        name: str | None = "Alice",
    ):
        payload: dict[str, str | None] = {
            "email": email,
            "password": password,
        }
        if name is not None:
            payload["name"] = name
        return self.client.post("/auth/register", json=payload)

    def _login(self, email: str, password: str):
        return self.client.post(
            "/auth/token",
            data={"username": email, "password": password},
        )

    def _auth_headers(self, email: str, password: str) -> dict[str, str]:
        response = self._login(email, password)
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # --- Registration (POST /auth/register) ---

    def test_register_normalizes_email_and_name_and_hides_password_hash(self):
        response = self._register(
            email="  Alice@Example.COM  ",
            password="secret123",
            name="  Alice  ",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["email"], "alice@example.com")
        self.assertEqual(body["name"], "Alice")
        self.assertFalse(body["disabled"])
        self.assertNotIn("passwordHash", body)

        stored = auth_service._load_users()[body["id"]]
        self.assertEqual(stored["email"], "alice@example.com")
        self.assertNotEqual(stored["passwordHash"], "secret123")
        self.assertTrue(
            auth_service.verify_password("secret123", stored["passwordHash"])
        )

    def test_register_rejects_missing_or_short_credentials(self):
        cases = [
            ("empty_email", {"email": "   ", "password": "secret123"}, 400),
            ("null_email", {"email": None, "password": "secret123"}, 422),
            ("missing_email", {"password": "secret123"}, 422),
            ("empty_password", {"email": "alice@example.com", "password": ""}, 400),
            ("null_password", {"email": "alice@example.com", "password": None}, 422),
            (
                "short_password",
                {"email": "alice@example.com", "password": "12345"},
                400,
            ),
        ]

        for label, payload, expected_status in cases:
            with self.subTest(case=label):
                response = self.client.post("/auth/register", json=payload)
                self.assertEqual(response.status_code, expected_status)

    def test_register_rejects_duplicate_email_case_insensitively(self):
        first = self._register(email="alice@example.com", password="secret123")
        self.assertEqual(first.status_code, 200)

        duplicate = self._register(
            email="  ALICE@Example.com ", password="other-password"
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["detail"], "User already exists")

    # --- Login & token issuance (POST /auth/token) ---

    def test_login_returns_bearer_token_for_case_insensitive_email(self):
        self.assertEqual(self._register().status_code, 200)

        response = self._login("  ALICE@Example.com  ", "secret123")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertTrue(body["access_token"])

    def test_login_rejects_wrong_password_and_unknown_email_uniformly(self):
        self.assertEqual(self._register().status_code, 200)

        wrong_password = self._login("alice@example.com", "wrong-pass")
        unknown_email = self._login("missing@example.com", "secret123")

        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(unknown_email.status_code, 400)
        self.assertEqual(
            wrong_password.json()["detail"],
            unknown_email.json()["detail"],
        )

    # --- JWT authentication & GET /auth/me ---

    def test_me_returns_authenticated_user_without_password_hash(self):
        registered = self._register(
            email="alice@example.com",
            password="secret123",
            name="Alice",
        ).json()
        headers = self._auth_headers("alice@example.com", "secret123")

        response = self.client.get("/auth/me", headers=headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], registered["id"])
        self.assertEqual(body["email"], "alice@example.com")
        self.assertEqual(body["name"], "Alice")
        self.assertNotIn("passwordHash", body)

    def test_me_rejects_missing_and_invalid_tokens(self):
        registered = self._register().json()
        wrong_secret_token = jwt.encode(
            {"sub": registered["id"]},
            "wrong-signing-secret-that-is-at-least-32-bytes",
            algorithm=auth_service.ALGORITHM,
        )
        expired_token = auth_service.create_access_token(
            {"sub": registered["id"]},
            expires_delta=timedelta(seconds=-5),
        )
        no_sub_token = auth_service.create_access_token({"scope": "read"})
        unknown_user_token = auth_service.create_access_token(
            {"sub": "deleted-user-id"}
        )

        cases = [
            ("missing_header", {}),
            ("malformed_jwt", {"Authorization": "Bearer not-a-jwt"}),
            ("wrong_secret", {"Authorization": f"Bearer {wrong_secret_token}"}),
            ("expired_token", {"Authorization": f"Bearer {expired_token}"}),
            ("missing_sub", {"Authorization": f"Bearer {no_sub_token}"}),
            ("unknown_user", {"Authorization": f"Bearer {unknown_user_token}"}),
        ]

        for label, headers in cases:
            with self.subTest(case=label):
                response = self.client.get("/auth/me", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers.get("www-authenticate"), "Bearer")

    def test_disabled_user_is_rejected_on_protected_routes(self):
        registered = self._register().json()
        headers = self._auth_headers("alice@example.com", "secret123")

        users = auth_service._load_users()
        users[registered["id"]]["disabled"] = True
        auth_service._save_users(users)

        me_response = self.client.get("/auth/me", headers=headers)
        password_response = self.client.put(
            "/auth/password",
            headers=headers,
            json={"currentPassword": "secret123", "newPassword": "new-secret123"},
        )

        self.assertEqual(me_response.status_code, 400)
        self.assertEqual(me_response.json()["detail"], "Inactive user")
        self.assertEqual(password_response.status_code, 400)
        self.assertEqual(password_response.json()["detail"], "Inactive user")

    # --- Password management (PUT /auth/password) ---

    def test_authenticated_user_can_change_password_and_relogin(self):
        self.assertEqual(self._register().status_code, 200)
        headers = self._auth_headers("alice@example.com", "secret123")

        response = self.client.put(
            "/auth/password",
            headers=headers,
            json={
                "currentPassword": "secret123",
                "newPassword": "new-password-456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._login("alice@example.com", "secret123").status_code, 400)
        self.assertEqual(
            self._login("alice@example.com", "new-password-456").status_code,
            200,
        )

    def test_password_change_rejects_wrong_current_and_short_new_password(self):
        self.assertEqual(self._register().status_code, 200)
        headers = self._auth_headers("alice@example.com", "secret123")

        wrong_current = self.client.put(
            "/auth/password",
            headers=headers,
            json={"currentPassword": "incorrect", "newPassword": "new-password-456"},
        )
        short_new = self.client.put(
            "/auth/password",
            headers=headers,
            json={"currentPassword": "secret123", "newPassword": "12345"},
        )

        self.assertEqual(wrong_current.status_code, 400)
        self.assertEqual(short_new.status_code, 400)
        self.assertEqual(self._login("alice@example.com", "secret123").status_code, 200)

    def test_password_change_requires_authentication(self):
        response = self.client.put(
            "/auth/password",
            json={"currentPassword": "secret123", "newPassword": "new-password-456"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
