import asyncio
from typing import List, Optional

import pytest
from fastapi_users import models
from pydantic import UUID4
from sqlmodel import Field, Relationship

from fastapi_users_db_sqlmodel import SQLModelBaseOAuthAccount, SQLModelBaseUserDB


class User(models.BaseUser):
    first_name: Optional[str]


class UserCreate(models.BaseUserCreate):
    first_name: Optional[str]


class UserUpdate(models.BaseUserUpdate):
    pass


class UserDB(SQLModelBaseUserDB, User, table=True):
    class Config:
        orm_mode = True


class UserOAuth(User):
    pass


class UserDBOAuth(SQLModelBaseUserDB, table=True):
    __tablename__ = "user"
    oauth_accounts: List["OAuthAccount"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "joined", "cascade": "all, delete"},
    )


class OAuthAccount(SQLModelBaseOAuthAccount, table=True):
    user_id: UUID4 = Field(foreign_key="user.id")
    user: Optional[UserDBOAuth] = Relationship(back_populates="oauth_accounts")


@pytest.fixture(scope="session")
def event_loop():
    """Force the pytest-asyncio loop to be the main one."""
    loop = asyncio.get_event_loop()
    yield loop


@pytest.fixture
def oauth_account1() -> OAuthAccount:
    return OAuthAccount(
        oauth_name="service1",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="user_oauth1",
        account_email="king.arthur@camelot.bt",
    )


@pytest.fixture
def oauth_account2() -> OAuthAccount:
    return OAuthAccount(
        oauth_name="service2",
        access_token="TOKEN",
        expires_at=1579000751,
        account_id="user_oauth2",
        account_email="king.arthur@camelot.bt",
    )
