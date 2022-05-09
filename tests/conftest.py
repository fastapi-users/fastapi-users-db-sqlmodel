import asyncio
from typing import Any, Dict, List, Optional

import pytest
from pydantic import UUID4
from sqlmodel import Field, Relationship

from fastapi_users_db_sqlmodel import SQLModelBaseOAuthAccount, SQLModelBaseUserDB


class User(SQLModelBaseUserDB, table=True):
    first_name: Optional[str]


class UserOAuth(SQLModelBaseUserDB, table=True):
    __tablename__ = "user_oauth"
    oauth_accounts: List["OAuthAccount"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )


class OAuthAccount(SQLModelBaseOAuthAccount, table=True):
    user_id: UUID4 = Field(foreign_key="user_oauth.id")
    user: Optional[UserOAuth] = Relationship(back_populates="oauth_accounts")


@pytest.fixture(scope="session")
def event_loop():
    """Force the pytest-asyncio loop to be the main one."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def oauth_account1() -> Dict[str, Any]:
    return {
        "oauth_name": "service1",
        "access_token": "TOKEN",
        "expires_at": 1579000751,
        "account_id": "user_oauth1",
        "account_email": "king.arthur@camelot.bt",
    }


@pytest.fixture
def oauth_account2() -> Dict[str, Any]:
    return {
        "oauth_name": "service2",
        "access_token": "TOKEN",
        "expires_at": 1579000751,
        "account_id": "user_oauth2",
        "account_email": "king.arthur@camelot.bt",
    }
