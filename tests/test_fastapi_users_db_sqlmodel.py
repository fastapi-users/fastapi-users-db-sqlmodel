import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.future import Engine
from sqlmodel import SQLModel, create_engine

from fastapi_users_db_sqlmodel import (
    NotSetOAuthAccountTableError,
    SQLModelUserDatabase,
    SQLModelUserDatabaseAsync,
)
from tests.conftest import OAuthAccount, UserDB, UserDBOAuth


safe_uuid = uuid.UUID("a9089e5d-2642-406d-a7c0-cbc641aca0ec")

async def init_sync_engine(url: str) -> AsyncGenerator[Engine, None]:
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


async def init_async_engine(url: str) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        yield engine
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture(
    params=[
        (init_sync_engine, "sqlite:///./test-sqlmodel-user.db", SQLModelUserDatabase),
        (
            init_async_engine,
            "sqlite+aiosqlite:///./test-sqlmodel-user.db",
            SQLModelUserDatabaseAsync,
        ),
    ]
)
async def sqlmodel_user_db(request) -> AsyncGenerator[SQLModelUserDatabase, None]:
    create_engine = request.param[0]
    database_url = request.param[1]
    database_class = request.param[2]
    async for engine in create_engine(database_url):
        yield database_class(UserDB, engine)


@pytest.fixture(
    params=[
        (
            init_sync_engine,
            "sqlite:///./test-sqlmodel-user-oauth.db",
            SQLModelUserDatabase,
        ),
        (
            init_async_engine,
            "sqlite+aiosqlite:///./test-sqlmodel-user-oauth.db",
            SQLModelUserDatabaseAsync,
        ),
    ]
)
async def sqlmodel_user_db_oauth(request) -> AsyncGenerator[SQLModelUserDatabase, None]:
    create_engine = request.param[0]
    database_url = request.param[1]
    database_class = request.param[2]
    async for engine in create_engine(database_url):
        yield database_class(UserDBOAuth, engine, OAuthAccount)


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries(sqlmodel_user_db: SQLModelUserDatabase[UserDB, OAuthAccount]):
    user = UserDB(
        id=safe_uuid,
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
            UserDB(id=safe_uuid, email=user_db.email, hashed_password="guinevere")
        )

    # Exception when inserting non-nullable fields
    with pytest.raises(exc.IntegrityError):
        wrong_user = UserDB(id=safe_uuid, email="lancelot@camelot.bt", hashed_password="aaa")
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
        id=safe_uuid,
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
        id=safe_uuid,
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
