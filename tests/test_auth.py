"""
Tests du système d'authentification et de gestion des utilisateurs pour ToAD.

Exécutez avec : pytest tests/test_auth.py -v
"""

import os
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web"))

os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-32chars!!"
os.environ["JWT_EXPIRATION_HOURS"] = "1"
os.environ["ADMIN_DEFAULT_PASSWORD"] = "testadminpass"
os.environ["ADMIN_DEFAULT_USERNAME"] = "testadmin"
os.environ["API_TOKEN"] = ""

TEST_DB = Path("/tmp/toad_test_auth.db")


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_toad_users.db"
    monkeypatch.setattr("app.DB_PATH", db_path)
    from app import init_db, ensure_default_admin, DB_PATH
    init_db()
    ensure_default_admin()
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app import app
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    r = client.post("/api/auth/login", json={"username": "testadmin", "password": "testadminpass"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _create_user(client, headers, username="testuser", password="testpass123", role="user"):
    return client.post("/api/users", json={
        "username": username,
        "password": password,
        "role": role,
    }, headers=headers)


class TestDatabaseInit:
    def test_db_tables_created(self, setup_test_db):
        conn = sqlite3.connect(str(setup_test_db))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "users" in table_names

    def test_default_admin_created(self, setup_test_db):
        conn = sqlite3.connect(str(setup_test_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE username = 'testadmin'").fetchone()
        conn.close()
        assert row is not None
        assert row["role"] == "admin"
        assert row["is_active"] == 1

    def test_default_admin_not_duplicated(self, setup_test_db):
        from app import ensure_default_admin
        ensure_default_admin()
        ensure_default_admin()
        conn = sqlite3.connect(str(setup_test_db))
        count = conn.execute("SELECT COUNT(*) FROM users WHERE username = 'testadmin'").fetchone()[0]
        conn.close()
        assert count == 1


class TestAuthLogin:
    def test_login_success(self, client):
        r = client.post("/api/auth/login", json={"username": "testadmin", "password": "testadminpass"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "testadmin"
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self, client):
        r = client.post("/api/auth/login", json={"username": "testadmin", "password": "wrongpass"})
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        r = client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
        assert r.status_code == 401

    def test_login_missing_fields(self, client):
        r = client.post("/api/auth/login", json={"username": "testadmin"})
        assert r.status_code == 422

    def test_login_inactive_user(self, client, admin_headers, setup_test_db):
        r = _create_user(client, admin_headers, username="inactiveuser")
        user_id = r.json()["id"]
        client.put(f"/api/users/{user_id}", json={"is_active": False}, headers=admin_headers)
        r = client.post("/api/auth/login", json={"username": "inactiveuser", "password": "testpass123"})
        assert r.status_code == 401
        assert "désactivé" in r.json()["detail"]


class TestAuthMe:
    def test_me_authenticated(self, client, admin_headers):
        r = client.get("/api/auth/me", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"

    def test_me_no_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401


class TestAuthLogout:
    def test_logout(self, client, admin_headers):
        r = client.post("/api/auth/logout", headers=admin_headers)
        assert r.status_code == 200


class TestTokenValidation:
    def test_expired_token(self, client, monkeypatch):
        from app import create_access_token
        from datetime import timedelta
        token = create_access_token({"sub": "1", "username": "test", "role": "admin"}, expires_delta=timedelta(seconds=-1))
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_malformed_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_empty_bearer(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer "})
        assert r.status_code == 401

    def test_no_authorization_header(self, client):
        r = client.get("/api/audits")
        assert r.status_code == 401


class TestUserCRUD:
    def test_create_user(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="newuser", password="securepass1")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_create_duplicate_user(self, client, admin_headers):
        _create_user(client, admin_headers, username="dupuser")
        r = _create_user(client, admin_headers, username="dupuser")
        assert r.status_code == 409

    def test_create_user_invalid_role(self, client, admin_headers):
        r = client.post("/api/users", json={
            "username": "badrole",
            "password": "securepass1",
            "role": "superadmin",
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_create_user_short_password(self, client, admin_headers):
        r = client.post("/api/users", json={
            "username": "shortpw",
            "password": "abc",
            "role": "user",
        }, headers=admin_headers)
        assert r.status_code == 422

    def test_list_users(self, client, admin_headers):
        _create_user(client, admin_headers, username="listuser1")
        _create_user(client, admin_headers, username="listuser2")
        r = client.get("/api/users", headers=admin_headers)
        assert r.status_code == 200
        users = r.json()
        usernames = [u["username"] for u in users]
        assert "listuser1" in usernames
        assert "listuser2" in usernames

    def test_update_user(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="updateuser")
        user_id = r.json()["id"]
        r = client.put(f"/api/users/{user_id}", json={"role": "admin"}, headers=admin_headers)
        assert r.status_code == 200
        r = client.get("/api/users", headers=admin_headers)
        updated = [u for u in r.json() if u["id"] == user_id][0]
        assert updated["role"] == "admin"

    def test_update_user_invalid_role(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="updbadrole")
        user_id = r.json()["id"]
        r = client.put(f"/api/users/{user_id}", json={"role": "god"}, headers=admin_headers)
        assert r.status_code == 400

    def test_update_nonexistent_user(self, client, admin_headers):
        r = client.put("/api/users/9999", json={"role": "user"}, headers=admin_headers)
        assert r.status_code == 404

    def test_delete_user(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="deleteuser")
        user_id = r.json()["id"]
        r = client.delete(f"/api/users/{user_id}", headers=admin_headers)
        assert r.status_code == 200
        r = client.get("/api/users", headers=admin_headers)
        ids = [u["id"] for u in r.json()]
        assert user_id not in ids

    def test_delete_nonexistent_user(self, client, admin_headers):
        r = client.delete("/api/users/9999", headers=admin_headers)
        assert r.status_code == 404

    def test_cannot_delete_self(self, client, admin_headers, admin_token):
        from app import decode_token
        payload = decode_token(admin_token)
        admin_id = int(payload["sub"])
        r = client.delete(f"/api/users/{admin_id}", headers=admin_headers)
        assert r.status_code == 400

    def test_reset_password(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="resetpw", password="oldpass123")
        user_id = r.json()["id"]
        r = client.post(f"/api/users/{user_id}/reset-password", json={"new_password": "newpass456"}, headers=admin_headers)
        assert r.status_code == 200
        r = client.post("/api/auth/login", json={"username": "resetpw", "password": "newpass456"})
        assert r.status_code == 200

    def test_reset_password_short(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="resetpwshort")
        user_id = r.json()["id"]
        r = client.post(f"/api/users/{user_id}/reset-password", json={"new_password": "ab"}, headers=admin_headers)
        assert r.status_code == 422


class TestRolePermissions:
    def test_admin_can_manage_users(self, client, admin_headers):
        r = client.get("/api/users", headers=admin_headers)
        assert r.status_code == 200

    def test_user_cannot_manage_users(self, client, admin_headers):
        _create_user(client, admin_headers, username="regularuser", role="user")
        r = client.post("/api/auth/login", json={"username": "regularuser", "password": "testpass123"})
        user_token = r.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        r = client.get("/api/users", headers=user_headers)
        assert r.status_code == 403

        r = client.post("/api/users", json={"username": "another", "password": "pass12345"}, headers=user_headers)
        assert r.status_code == 403

        r = client.delete("/api/users/1", headers=user_headers)
        assert r.status_code == 403

    def test_viewer_cannot_manage_users(self, client, admin_headers):
        _create_user(client, admin_headers, username="vieweruser", role="viewer")
        r = client.post("/api/auth/login", json={"username": "vieweruser", "password": "testpass123"})
        viewer_token = r.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        r = client.get("/api/users", headers=viewer_headers)
        assert r.status_code == 403

    def test_user_can_access_audits(self, client, admin_headers):
        _create_user(client, admin_headers, username="audituser", role="user")
        r = client.post("/api/auth/login", json={"username": "audituser", "password": "testpass123"})
        user_token = r.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        r = client.get("/api/audits", headers=user_headers)
        assert r.status_code == 200

    def test_viewer_can_access_audits(self, client, admin_headers):
        _create_user(client, admin_headers, username="viewaudit", role="viewer")
        r = client.post("/api/auth/login", json={"username": "viewaudit", "password": "testpass123"})
        viewer_token = r.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        r = client.get("/api/audits", headers=viewer_headers)
        assert r.status_code == 200

    def test_inactive_user_rejected(self, client, admin_headers):
        r = _create_user(client, admin_headers, username="deactivated")
        user_id = r.json()["id"]
        client.put(f"/api/users/{user_id}", json={"is_active": False}, headers=admin_headers)

        r = client.post("/api/auth/login", json={"username": "deactivated", "password": "testpass123"})
        assert r.status_code == 401


class TestLegacyAPIToken:
    def test_legacy_token_still_works(self, client, monkeypatch):
        import app as app_module
        old_val = app_module.API_TOKEN
        app_module.API_TOKEN = "legacy-test-token"
        try:
            r = client.get("/api/audits", headers={"Authorization": "Bearer legacy-test-token"})
            assert r.status_code == 200
        finally:
            app_module.API_TOKEN = old_val

    def test_legacy_token_invalid(self, client, monkeypatch):
        import app as app_module
        old_val = app_module.API_TOKEN
        app_module.API_TOKEN = "legacy-test-token"
        try:
            r = client.get("/api/audits", headers={"Authorization": "Bearer wrong-token"})
            assert r.status_code == 401
        finally:
            app_module.API_TOKEN = old_val


class TestPublicEndpoints:
    def test_health_no_auth(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_login_no_auth(self, client):
        r = client.post("/api/auth/login", json={"username": "testadmin", "password": "testadminpass"})
        assert r.status_code == 200

    def test_setup_status_no_auth(self, client):
        r = client.get("/api/setup/status")
        assert r.status_code == 200


class TestPasswordSecurity:
    def test_passwords_are_hashed(self, setup_test_db):
        conn = sqlite3.connect(str(setup_test_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT password_hash FROM users WHERE username = 'testadmin'").fetchone()
        conn.close()
        assert row["password_hash"] != "testadminpass"
        assert row["password_hash"].startswith("$2")

    def test_password_not_in_login_response(self, client):
        r = client.post("/api/auth/login", json={"username": "testadmin", "password": "testadminpass"})
        data = r.json()
        assert "password" not in data
        assert "password_hash" not in data

    def test_password_not_in_me_response(self, client, admin_headers):
        r = client.get("/api/auth/me", headers=admin_headers)
        data = r.json()
        assert "password" not in data
        assert "password_hash" not in data

    def test_password_not_in_list_users(self, client, admin_headers):
        r = client.get("/api/users", headers=admin_headers)
        for user in r.json():
            assert "password_hash" not in user
            assert "password" not in user


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
