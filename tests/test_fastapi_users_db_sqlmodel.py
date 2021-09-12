from typing import AsyncGenerator

import pytest
from sqlalchemy import exc
from sqlmodel import SQLModel, create_engine

from fastapi_users_db_sqlmodel import NotSetOAuthAccountTableError, SQLModelUserDatabase
from tests.conftest import OAuthAccount, UserDB, UserDBOAuth


@pytest.fixture
async def sqlmodel_user_db() -> AsyncGenerator[SQLModelUserDatabase, None]:
    DATABASE_URL = "sqlite:///./test-sqlmodel-user.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    yield SQLModelUserDatabase(UserDB, engine)

    SQLModel.metadata.drop_all(engine)


@pytest.fixture
async def sqlmodel_user_db_oauth() -> AsyncGenerator[SQLModelUserDatabase, None]:
    DATABASE_URL = "sqlite:///./test-sqlmodel-user-oauth.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    yield SQLModelUserDatabase(UserDBOAuth, engine, OAuthAccount)

    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries(sqlmodel_user_db: SQLModelUserDatabase[UserDB, OAuthAccount]):
    user = UserDB(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
    )

    # Create
    user_db = await sqlmodel_user_db.create(user)
    assert user_db.id is not None
    assert user_db.is_active is True
    assert user_db.is_superuser is False
    assert user_db.email == user.email

    # Update
    user_db.is_superuser = True
    await sqlmodel_user_db.update(user_db)

    # Get by id
    id_user = await sqlmodel_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user_db.id
    assert id_user.is_superuser is True

    # Get by email
    email_user = await sqlmodel_user_db.get_by_email(str(user.email))
    assert email_user is not None
    assert email_user.id == user_db.id

    # Get by uppercased email
    email_user = await sqlmodel_user_db.get_by_email("Lancelot@camelot.bt")
    assert email_user is not None
    assert email_user.id == user_db.id

    # Exception when inserting existing email
    with pytest.raises(exc.IntegrityError):
        await sqlmodel_user_db.create(
            UserDB(email=user_db.email, hashed_password="guinevere")
        )

    # Exception when inserting non-nullable fields
    with pytest.raises(exc.IntegrityError):
        wrong_user = UserDB(email="lancelot@camelot.bt", hashed_password="aaa")
        wrong_user.email = None  # type: ignore
        await sqlmodel_user_db.create(wrong_user)

    # Unknown user
    unknown_user = await sqlmodel_user_db.get_by_email("galahad@camelot.bt")
    assert unknown_user is None

    # Delete user
    await sqlmodel_user_db.delete(user)
    deleted_user = await sqlmodel_user_db.get(user.id)
    assert deleted_user is None

    # Exception when trying to get by OAuth account
    with pytest.raises(NotSetOAuthAccountTableError):
        await sqlmodel_user_db.get_by_oauth_account("foo", "bar")


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries_custom_fields(
    sqlmodel_user_db: SQLModelUserDatabase[UserDB, OAuthAccount],
):
    """It should output custom fields in query result."""
    user = UserDB(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
        first_name="Lancelot",
    )
    await sqlmodel_user_db.create(user)

    id_user = await sqlmodel_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.first_name == user.first_name


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries_oauth(
    sqlmodel_user_db_oauth: SQLModelUserDatabase[UserDBOAuth, OAuthAccount],
    oauth_account1,
    oauth_account2,
):
    user = UserDBOAuth(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
        oauth_accounts=[oauth_account1, oauth_account2],
    )

    # Create
    user_db = await sqlmodel_user_db_oauth.create(user)
    assert user_db.id is not None
    assert hasattr(user_db, "oauth_accounts")
    assert len(user_db.oauth_accounts) == 2

    # Update
    user_db.oauth_accounts[0].access_token = "NEW_TOKEN"
    await sqlmodel_user_db_oauth.update(user_db)

    # Get by id
    id_user = await sqlmodel_user_db_oauth.get(user.id)
    assert id_user is not None
    assert id_user.id == user_db.id
    assert id_user.oauth_accounts[0].access_token == "NEW_TOKEN"

    # Get by email
    email_user = await sqlmodel_user_db_oauth.get_by_email(str(user.email))
    assert email_user is not None
    assert email_user.id == user_db.id
    assert len(email_user.oauth_accounts) == 2

    # Get by OAuth account
    oauth_user = await sqlmodel_user_db_oauth.get_by_oauth_account(
        oauth_account1.oauth_name, oauth_account1.account_id
    )
    assert oauth_user is not None
    assert oauth_user.id == user.id
    assert len(oauth_user.oauth_accounts) == 2

    # Unknown OAuth account
    unknown_oauth_user = await sqlmodel_user_db_oauth.get_by_oauth_account("foo", "bar")
    assert unknown_oauth_user is None
