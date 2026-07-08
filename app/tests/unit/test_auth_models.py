from app.modules.auth.models import RefreshToken, User


def test_user_email_is_unique_and_indexed() -> None:
    table = User.__table__

    unique_columns = {
        column.name
        for constraint in table.constraints
        if constraint.name == "uq_users_email"
        for column in constraint.columns
    }
    indexed_columns = {
        column.name
        for index in table.indexes
        if index.name == "ix_users_email"
        for column in index.columns
    }

    assert unique_columns == {"email"}
    assert indexed_columns == {"email"}


def test_user_stores_password_hash_not_plaintext_password() -> None:
    columns = set(User.__table__.columns.keys())

    assert "password_hash" in columns
    assert "password" not in columns
    assert "plain_password" not in columns


def test_refresh_token_stores_hash_only() -> None:
    columns = set(RefreshToken.__table__.columns.keys())

    assert "token_hash" in columns
    assert "token" not in columns
    assert "refresh_token" not in columns
    assert "plain_token" not in columns


def test_refresh_token_hash_is_indexed() -> None:
    indexed_columns = {
        column.name
        for index in RefreshToken.__table__.indexes
        if index.name == "ix_refresh_tokens_token_hash"
        for column in index.columns
    }

    assert indexed_columns == {"token_hash"}

