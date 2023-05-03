"""FastAPI Users database adapter for SQLModel."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Type

from fastapi_users.db.base import BaseUserDatabase
from fastapi_users.models import ID, OAP, UP
from pydantic import UUID4, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import Field, Session, SQLModel, func, select

__version__ = "0.3.0"


class SQLModelBaseUserDB(SQLModel):
    __tablename__ = "user"

    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    if TYPE_CHECKING:  # pragma: no cover
        email: str
    else:
        email: EmailStr = Field(
            sa_column_kwargs={"unique": True, "index": True}, nullable=False
        )
    hashed_password: str

    is_active: bool = Field(True, nullable=False)
    is_superuser: bool = Field(False, nullable=False)
    is_verified: bool = Field(False, nullable=False)

    class Config:
        orm_mode = True


class SQLModelBaseOAuthAccount(SQLModel):
    __tablename__ = "oauthaccount"

    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: UUID4 = Field(foreign_key="user.id", nullable=False)
    oauth_name: str = Field(index=True, nullable=False)
    access_token: str = Field(nullable=False)
    expires_at: Optional[int] = Field(nullable=True)
    refresh_token: Optional[str] = Field(nullable=True)
    account_id: str = Field(index=True, nullable=False)
    account_email: str = Field(nullable=False)

    class Config:
        orm_mode = True


class SQLModelUserDatabase(Generic[UP, ID], BaseUserDatabase[UP, ID]):
    """
    Database adapter for SQLModel.

    :param session: SQLAlchemy session.
    """

    session: Session
    user_model: Type[UP]
    oauth_account_model: Optional[Type[SQLModelBaseOAuthAccount]]

    def __init__(
        self,
        session: Session,
        user_model: Type[UP],
        oauth_account_model: Optional[Type[SQLModelBaseOAuthAccount]] = None,
    ):
        self.session = session
        self.user_model = user_model
        self.oauth_account_model = oauth_account_model

    async def get(self, id: ID) -> Optional[UP]:
        """Get a single user by id."""
        return self.session.get(self.user_model, id)

    async def get_by_email(self, email: str) -> Optional[UP]:
        """Get a single user by email."""
        statement = select(self.user_model).where(  # type: ignore
            func.lower(self.user_model.email) == func.lower(email)
        )
        results = self.session.exec(statement)
        return results.first()

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UP]:
        """Get a single user by OAuth account id."""
        if self.oauth_account_model is None:
            raise NotImplementedError()
        statement = (
            select(self.oauth_account_model)
            .where(self.oauth_account_model.oauth_name == oauth)
            .where(self.oauth_account_model.account_id == account_id)
        )
        results = self.session.exec(statement)
        oauth_account = results.first()
        if oauth_account:
            user = oauth_account.user  # type: ignore
            return user
        return None

    async def create(self, create_dict: Dict[str, Any]) -> UP:
        """Create a user."""
        user = self.user_model(**create_dict)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def update(self, user: UP, update_dict: Dict[str, Any]) -> UP:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def delete(self, user: UP) -> None:
        self.session.delete(user)
        self.session.commit()

    async def add_oauth_account(self, user: UP, create_dict: Dict[str, Any]) -> UP:
        if self.oauth_account_model is None:
            raise NotImplementedError()

        oauth_account = self.oauth_account_model(**create_dict)
        user.oauth_accounts.append(oauth_account)  # type: ignore
        self.session.add(user)

        self.session.commit()

        return user

    async def update_oauth_account(
        self, user: UP, oauth_account: OAP, update_dict: Dict[str, Any]
    ) -> UP:
        if self.oauth_account_model is None:
            raise NotImplementedError()

        for key, value in update_dict.items():
            setattr(oauth_account, key, value)
        self.session.add(oauth_account)
        self.session.commit()

        return user


class SQLModelUserDatabaseAsync(Generic[UP, ID], BaseUserDatabase[UP, ID]):
    """
    Database adapter for SQLModel working purely asynchronously.

    :param user_model: SQLModel model of a DB representation of a user.
    :param session: SQLAlchemy async session.
    """

    session: AsyncSession
    user_model: Type[UP]
    oauth_account_model: Optional[Type[SQLModelBaseOAuthAccount]]

    def __init__(
        self,
        session: AsyncSession,
        user_model: Type[UP],
        oauth_account_model: Optional[Type[SQLModelBaseOAuthAccount]] = None,
    ):
        self.session = session
        self.user_model = user_model
        self.oauth_account_model = oauth_account_model

    async def get(self, id: ID) -> Optional[UP]:
        """Get a single user by id."""
        return await self.session.get(self.user_model, id)

    async def get_by_email(self, email: str) -> Optional[UP]:
        """Get a single user by email."""
        statement = select(self.user_model).where(  # type: ignore
            func.lower(self.user_model.email) == func.lower(email)
        )
        results = await self.session.execute(statement)
        object = results.first()
        if object is None:
            return None
        return object[0]

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UP]:
        """Get a single user by OAuth account id."""
        if self.oauth_account_model is None:
            raise NotImplementedError()
        statement = (
            select(self.oauth_account_model)
            .where(self.oauth_account_model.oauth_name == oauth)
            .where(self.oauth_account_model.account_id == account_id)
            .options(selectinload(self.oauth_account_model.user))  # type: ignore
        )
        results = await self.session.execute(statement)
        oauth_account = results.first()
        if oauth_account:
            user = oauth_account[0].user  # type: ignore
            return user
        return None

    async def create(self, create_dict: Dict[str, Any]) -> UP:
        """Create a user."""
        user = self.user_model(**create_dict)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: UP, update_dict: Dict[str, Any]) -> UP:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: UP) -> None:
        await self.session.delete(user)
        await self.session.commit()

    async def add_oauth_account(self, user: UP, create_dict: Dict[str, Any]) -> UP:
        if self.oauth_account_model is None:
            raise NotImplementedError()

        oauth_account = self.oauth_account_model(**create_dict)
        user.oauth_accounts.append(oauth_account)  # type: ignore
        self.session.add(user)

        await self.session.commit()

        return user

    async def update_oauth_account(
        self, user: UP, oauth_account: OAP, update_dict: Dict[str, Any]
    ) -> UP:
        if self.oauth_account_model is None:
            raise NotImplementedError()

        for key, value in update_dict.items():
            setattr(oauth_account, key, value)
        self.session.add(oauth_account)
        await self.session.commit()

        return user
