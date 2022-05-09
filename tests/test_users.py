import uuid
from typing import Any, AsyncGenerator, Dict

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from fastapi_users_db_sqlmodel import SQLModelUserDatabase, SQLModelUserDatabaseAsync
from tests.conftest import OAuthAccount, User, UserOAuth

safe_uuid = uuid.UUID("a9089e5d-2642-406d-a7c0-cbc641aca0ec")


async def init_sync_session(url: str) -> AsyncGenerator[Session, None]:
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


async def init_async_session(url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(url, connect_args={"check_same_thread": False})
    make_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        async with make_session() as session:
            yield session
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(
    params=[
        (init_sync_session, "sqlite:///./test-sqlmodel-user.db", SQLModelUserDatabase),
        (
            init_async_session,
            "sqlite+aiosqlite:///./test-sqlmodel-user.db",
            SQLModelUserDatabaseAsync,
        ),
    ],
    ids=["sync", "async"],
)
async def sqlmodel_user_db(request) -> AsyncGenerator[SQLModelUserDatabase, None]:
    create_session = request.param[0]
    database_url = request.param[1]
    database_class = request.param[2]
    async for session in create_session(database_url):
        yield database_class(session, User)


@pytest_asyncio.fixture(
    params=[
        (
            init_sync_session,
            "sqlite:///./test-sqlmodel-user-oauth.db",
            SQLModelUserDatabase,
        ),
        (
            init_async_session,
            "sqlite+aiosqlite:///./test-sqlmodel-user-oauth.db",
            SQLModelUserDatabaseAsync,
        ),
    ],
    ids=["sync", "async"],
)
async def sqlmodel_user_db_oauth(request) -> AsyncGenerator[SQLModelUserDatabase, None]:
    create_session = request.param[0]
    database_url = request.param[1]
    database_class = request.param[2]
    async for session in create_session(database_url):
        yield database_class(session, UserOAuth, OAuthAccount)


@pytest.mark.asyncio
async def test_queries(sqlmodel_user_db: SQLModelUserDatabase[User, UUID4]):
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
    }

    # Create
    user = await sqlmodel_user_db.create(user_create)
    assert user.id is not None
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.email == user_create["email"]

    # Update
    updated_user = await sqlmodel_user_db.update(user, {"is_superuser": True})
    assert updated_user.is_superuser is True

    # Get by id
    id_user = await sqlmodel_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.is_superuser is True

    # Get by email
    email_user = await sqlmodel_user_db.get_by_email(str(user_create["email"]))
    assert email_user is not None
    assert email_user.id == user.id

    # Get by uppercased email
    email_user = await sqlmodel_user_db.get_by_email("Lancelot@camelot.bt")
    assert email_user is not None
    assert email_user.id == user.id

    # Unknown user
    unknown_user = await sqlmodel_user_db.get_by_email("galahad@camelot.bt")
    assert unknown_user is None

    # Delete user
    await sqlmodel_user_db.delete(user)
    deleted_user = await sqlmodel_user_db.get(user.id)
    assert deleted_user is None

    # OAuth without defined table
    with pytest.raises(NotImplementedError):
        await sqlmodel_user_db.get_by_oauth_account("foo", "bar")
    with pytest.raises(NotImplementedError):
        await sqlmodel_user_db.add_oauth_account(user, {})
    with pytest.raises(NotImplementedError):
        oauth_account = OAuthAccount()
        await sqlmodel_user_db.update_oauth_account(user, oauth_account, {})


@pytest.mark.asyncio
async def test_insert_existing_email(
    sqlmodel_user_db: SQLModelUserDatabase[User, UUID4]
):
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
    }
    await sqlmodel_user_db.create(user_create)

    with pytest.raises(exc.IntegrityError):
        await sqlmodel_user_db.create(user_create)


@pytest.mark.asyncio
async def test_queries_custom_fields(
    sqlmodel_user_db: SQLModelUserDatabase[User, UUID4],
):
    """It should output custom fields in query result."""
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
        "first_name": "Lancelot",
    }
    user = await sqlmodel_user_db.create(user_create)

    id_user = await sqlmodel_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.first_name == user.first_name


@pytest.mark.asyncio
async def test_queries_oauth(
    sqlmodel_user_db_oauth: SQLModelUserDatabase[UserOAuth, UUID4],
    oauth_account1: Dict[str, Any],
    oauth_account2: Dict[str, Any],
):
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
    }

    # Create
    user = await sqlmodel_user_db_oauth.create(user_create)
    assert user.id is not None

    # Add OAuth account
    user = await sqlmodel_user_db_oauth.add_oauth_account(user, oauth_account1)
    user = await sqlmodel_user_db_oauth.add_oauth_account(user, oauth_account2)
    assert len(user.oauth_accounts) == 2
    assert user.oauth_accounts[1].account_id == oauth_account2["account_id"]
    assert user.oauth_accounts[0].account_id == oauth_account1["account_id"]

    # Update
    user = await sqlmodel_user_db_oauth.update_oauth_account(
        user, user.oauth_accounts[0], {"access_token": "NEW_TOKEN"}
    )
    assert user.oauth_accounts[0].access_token == "NEW_TOKEN"

    # Get by id
    id_user = await sqlmodel_user_db_oauth.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.oauth_accounts[0].access_token == "NEW_TOKEN"

    # Get by email
    email_user = await sqlmodel_user_db_oauth.get_by_email(user_create["email"])
    assert email_user is not None
    assert email_user.id == user.id
    assert len(email_user.oauth_accounts) == 2

    # Get by OAuth account
    oauth_user = await sqlmodel_user_db_oauth.get_by_oauth_account(
        oauth_account1["oauth_name"], oauth_account1["account_id"]
    )
    assert oauth_user is not None
    assert oauth_user.id == user.id

    # Unknown OAuth account
    unknown_oauth_user = await sqlmodel_user_db_oauth.get_by_oauth_account("foo", "bar")
    assert unknown_oauth_user is None
