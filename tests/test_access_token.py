import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from fastapi_users_db_sqlmodel import SQLModelUserDatabase, SQLModelUserDatabaseAsync
from fastapi_users_db_sqlmodel.access_token import (
    SQLModelAccessTokenDatabase,
    SQLModelAccessTokenDatabaseAsync,
    SQLModelBaseAccessToken,
)
from tests.conftest import User


class AccessToken(SQLModelBaseAccessToken, table=True):
    pass


@pytest.fixture
def user_id() -> UUID4:
    return uuid.UUID("a9089e5d-2642-406d-a7c0-cbc641aca0ec")


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
        (
            init_sync_session,
            "sqlite:///./test-sqlmodel-access-token.db",
            SQLModelAccessTokenDatabase,
            SQLModelUserDatabase,
        ),
        (
            init_async_session,
            "sqlite+aiosqlite:///./test-sqlmodel-access-token.db",
            SQLModelAccessTokenDatabaseAsync,
            SQLModelUserDatabaseAsync,
        ),
    ],
    ids=["sync", "async"],
)
async def sqlmodel_access_token_db(
    request, user_id: UUID4
) -> AsyncGenerator[SQLModelAccessTokenDatabase, None]:
    create_session = request.param[0]
    database_url = request.param[1]
    access_token_database_class = request.param[2]
    user_database_class = request.param[3]
    async for session in create_session(database_url):
        user_db = user_database_class(session, User)
        await user_db.create(
            {
                "id": user_id,
                "email": "lancelot@camelot.bt",
                "hashed_password": "guinevere",
            }
        )
        yield access_token_database_class(session, AccessToken)


@pytest.mark.asyncio
async def test_queries(
    sqlmodel_access_token_db: SQLModelAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token_create = {"token": "TOKEN", "user_id": user_id}

    # Create
    access_token = await sqlmodel_access_token_db.create(access_token_create)
    assert access_token.token == "TOKEN"
    assert access_token.user_id == user_id

    # Update
    update_dict = {"created_at": datetime.now(timezone.utc)}
    updated_access_token = await sqlmodel_access_token_db.update(
        access_token, update_dict
    )
    assert updated_access_token.created_at.replace(microsecond=0) == update_dict[
        "created_at"
    ].replace(microsecond=0)

    # Get by token
    access_token_by_token = await sqlmodel_access_token_db.get_by_token(
        access_token.token
    )
    assert access_token_by_token is not None

    # Get by token expired
    access_token_by_token = await sqlmodel_access_token_db.get_by_token(
        access_token.token, max_age=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert access_token_by_token is None

    # Get by token not expired
    access_token_by_token = await sqlmodel_access_token_db.get_by_token(
        access_token.token, max_age=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    assert access_token_by_token is not None

    # Get by token unknown
    access_token_by_token = await sqlmodel_access_token_db.get_by_token(
        "NOT_EXISTING_TOKEN"
    )
    assert access_token_by_token is None

    # Delete token
    await sqlmodel_access_token_db.delete(access_token)
    deleted_access_token = await sqlmodel_access_token_db.get_by_token(
        access_token.token
    )
    assert deleted_access_token is None


@pytest.mark.asyncio
async def test_insert_existing_token(
    sqlmodel_access_token_db: SQLModelAccessTokenDatabase[AccessToken], user_id: UUID4
):
    access_token_create = {"token": "TOKEN", "user_id": user_id}
    await sqlmodel_access_token_db.create(access_token_create)

    with pytest.raises(exc.IntegrityError):
        await sqlmodel_access_token_db.create(access_token_create)
