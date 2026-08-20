from apps.api.src.core.config import Settings


def test_settings_cors_origins_json_list():
    s = Settings(BACKEND_CORS_ORIGINS='["http://localhost:3000"]')
    assert s.BACKEND_CORS_ORIGINS == ["http://localhost:3000"]


def test_settings_cors_origins_comma_separated():
    s = Settings(BACKEND_CORS_ORIGINS="http://localhost:3000,http://app.local")
    assert s.BACKEND_CORS_ORIGINS == ["http://localhost:3000", "http://app.local"]


def test_settings_db_url_transformation():
    s = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db")
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")

    s2 = Settings(SYNC_DATABASE_URL="postgresql://user:pass@localhost:5432/db")
    assert s2.SYNC_DATABASE_URL.startswith("postgresql+psycopg2://")
