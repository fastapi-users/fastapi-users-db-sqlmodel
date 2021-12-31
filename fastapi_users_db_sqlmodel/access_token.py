from datetime import datetime, timezone
from typing import Generic, Optional, Type, TypeVar

from fastapi_users.authentication.strategy.db import AccessTokenDatabase
from fastapi_users.authentication.strategy.db.models import BaseAccessToken
from pydantic import UUID4
from sqlalchemy import Column, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, Session, SQLModel, select


def now_utc():
    return datetime.now(timezone.utc)


class SQLModelBaseAccessToken(BaseAccessToken, SQLModel):
    __tablename__ = "accesstoken"

    token: str = Field(
        sa_column=Column("token", types.String(length=43), primary_key=True)
    )
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(
            "created_at", types.DateTime(timezone=True), nullable=False, index=True
        ),
    )
    user_id: UUID4 = Field(foreign_key="user.id", nullable=False)

    class Config:
        orm_mode = True


A = TypeVar("A", bound=SQLModelBaseAccessToken)


class SQLModelAccessTokenDatabase(Generic[A], AccessTokenDatabase[A]):
    """
    Access token database adapter for SQLModel.

    :param user_db_model: SQLModel model of a DB representation of an access token.
    :param session: SQLAlchemy session.
    """

    def __init__(self, access_token_model: Type[A], session: Session):
        self.access_token_model = access_token_model
        self.session = session

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[A]:
        statement = select(self.access_token_model).where(
            self.access_token_model.token == token
        )
        if max_age is not None:
            statement = statement.where(self.access_token_model.created_at >= max_age)

        results = self.session.exec(statement)
        return results.first()

    async def create(self, access_token: A) -> A:
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    async def update(self, access_token: A) -> A:
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    async def delete(self, access_token: A) -> None:
        self.session.delete(access_token)
        self.session.commit()


class SQLModelAccessTokenDatabaseAsync(Generic[A], AccessTokenDatabase[A]):
    """
    Access token database adapter for SQLModel working purely asynchronously.

    :param user_db_model: SQLModel model of a DB representation of an access token.
    :param session: SQLAlchemy async session.
    """

    def __init__(self, access_token_model: Type[A], session: AsyncSession):
        self.access_token_model = access_token_model
        self.session = session

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[A]:
        statement = select(self.access_token_model).where(
            self.access_token_model.token == token
        )
        if max_age is not None:
            statement = statement.where(self.access_token_model.created_at >= max_age)

        results = await self.session.execute(statement)
        object = results.first()
        if object is None:
            return None
        return object[0]

    async def create(self, access_token: A) -> A:
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token

    async def update(self, access_token: A) -> A:
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token

    async def delete(self, access_token: A) -> None:
        await self.session.delete(access_token)
        await self.session.commit()
