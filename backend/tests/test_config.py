import pytest
from pydantic import ValidationError

from app.config import Settings

GOOD = {
    "environment": "production",
    "secret_key": "a" * 64,
    "admin_password": "a-long-admin-password",
    "database_url": "postgresql://u:strongpw@postgres:5432/db",
}


def test_production_accepts_real_secrets():
    Settings(**GOOD)


@pytest.mark.parametrize(
    "override, named",
    [
        ({"secret_key": "CHANGE_ME_openssl_rand_hex_32"}, "SECRET_KEY"),
        ({"secret_key": "short"}, "SECRET_KEY"),
        ({"admin_password": "CHANGE_ME_strong_admin_password"}, "ADMIN_PASSWORD"),
        ({"admin_password": "admin"}, "ADMIN_PASSWORD"),
        ({"database_url": "postgresql://u:CHANGE_ME@postgres:5432/db"}, "DATABASE_URL"),
    ],
)
def test_production_rejects_placeholders(override, named):
    with pytest.raises(ValidationError, match=named):
        Settings(**{**GOOD, **override})


def test_development_allows_defaults():
    Settings(environment="development", secret_key="dev", admin_password="admin")
