from datetime import datetime
from typing import Any, Dict, Generic, Optional, Type

from fastapi_users.authentication.strategy.db import AP, AccessTokenDatabase
from pydantic import UUID4
from sqlalchemy import Column, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, Session, SQLModel, select

from fastapi_users_db_sqlmodel.generics import TIMESTAMPAware, now_utc


class SQLModelBaseAccessToken(SQLModel):
    __tablename__ = "accesstoken"

    token: str = Field(
        sa_column=Column("token", types.String(length=43), primary_key=True)
    )
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(
            "created_at", TIMESTAMPAware(timezone=True), nullable=False, index=True
        ),
    )
    user_id: UUID4 = Field(foreign_key="user.id", nullable=False)

    class Config:
        orm_mode = True


class SQLModelAccessTokenDatabase(Generic[AP], AccessTokenDatabase[AP]):
    """
    Access token database adapter for SQLModel.

    :param session: SQLAlchemy session.
    :param access_token_model: SQLModel access token model.
    """

    def __init__(self, session: Session, access_token_model: Type[AP]):
        self.session = session
        self.access_token_model = access_token_model

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[AP]:
        statement = select(self.access_token_model).where(  # type: ignore
            self.access_token_model.token == token
        )
        if max_age is not None:
            statement = statement.where(self.access_token_model.created_at >= max_age)

        results = self.session.execute(statement)
        access_token = results.first()
        if access_token is None:
            return None
        return access_token[0]

    async def create(self, create_dict: Dict[str, Any]) -> AP:
        access_token = self.access_token_model(**create_dict)
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    async def update(self, access_token: AP, update_dict: Dict[str, Any]) -> AP:
        for key, value in update_dict.items():
            setattr(access_token, key, value)
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    async def delete(self, access_token: AP) -> None:
        self.session.delete(access_token)
        self.session.commit()


class SQLModelAccessTokenDatabaseAsync(Generic[AP], AccessTokenDatabase[AP]):
    """
    Access token database adapter for SQLModel working purely asynchronously.

    :param session: SQLAlchemy async session.
    :param access_token_model: SQLModel access token model.
    """

    def __init__(self, session: AsyncSession, access_token_model: Type[AP]):
        self.session = session
        self.access_token_model = access_token_model

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[AP]:
        statement = select(self.access_token_model).where(  # type: ignore
            self.access_token_model.token == token
        )
        if max_age is not None:
            statement = statement.where(self.access_token_model.created_at >= max_age)

        results = await self.session.execute(statement)
        access_token = results.first()
        if access_token is None:
            return None
        return access_token[0]

    async def create(self, create_dict: Dict[str, Any]) -> AP:
        access_token = self.access_token_model(**create_dict)
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token

    async def update(self, access_token: AP, update_dict: Dict[str, Any]) -> AP:
        for key, value in update_dict.items():
            setattr(access_token, key, value)
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token

    async def delete(self, access_token: AP) -> None:
        await self.session.delete(access_token)
        await self.session.commit()
