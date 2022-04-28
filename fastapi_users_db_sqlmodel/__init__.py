"""FastAPI Users database adapter for SQLModel."""
import uuid
from typing import Generic, Optional, Type, TypeVar

from fastapi_users.db.base import BaseUserDatabase
from fastapi_users.models import BaseOAuthAccount, BaseUserDB
from pydantic import UUID4, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import Field, Session, SQLModel, func, select

__version__ = "0.1.2"


class SQLModelBaseUserDB(BaseUserDB, SQLModel):
    __tablename__ = "user"

    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    email: EmailStr = Field(
        sa_column_kwargs={"unique": True, "index": True}, nullable=False
    )

    is_active: bool = Field(True, nullable=False)
    is_superuser: bool = Field(False, nullable=False)
    is_verified: bool = Field(False, nullable=False)

    class Config:
        orm_mode = True


class SQLModelBaseOAuthAccount(BaseOAuthAccount, SQLModel):
    __tablename__ = "oauthaccount"

    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: UUID4 = Field(foreign_key="user.id", nullable=False)

    class Config:
        orm_mode = True


UD = TypeVar("UD", bound=SQLModelBaseUserDB)
OA = TypeVar("OA", bound=SQLModelBaseOAuthAccount)


class NotSetOAuthAccountTableError(Exception):
    """
    OAuth table was not set in DB adapter but was needed.

    Raised when trying to create/update a user with OAuth accounts set
    but no table were specified in the DB adapter.
    """

    pass


class SQLModelUserDatabase(Generic[UD, OA], BaseUserDatabase[UD]):
    """
    Database adapter for SQLModel.

    :param user_db_model: SQLModel model of a DB representation of a user.
    :param session: SQLAlchemy session.
    """

    session: Session
    oauth_account_model: Optional[Type[OA]]

    def __init__(
        self,
        user_db_model: Type[UD],
        session: Session,
        oauth_account_model: Optional[Type[OA]] = None,
    ):
        super().__init__(user_db_model)
        self.session = session
        self.oauth_account_model = oauth_account_model

    async def get(self, id: UUID4) -> Optional[UD]:
        """Get a single user by id."""
        return self.session.get(self.user_db_model, id)

    async def get_by_email(self, email: str) -> Optional[UD]:
        """Get a single user by email."""
        statement = select(self.user_db_model).where(
            func.lower(self.user_db_model.email) == func.lower(email)
        )
        results = self.session.exec(statement)
        return results.first()

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UD]:
        """Get a single user by OAuth account id."""
        if not self.oauth_account_model:
            raise NotSetOAuthAccountTableError()
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

    async def create(self, user: UD) -> UD:
        """Create a user."""
        self.session.add(user)
        if self.oauth_account_model is not None:
            for oauth_account in user.oauth_accounts:  # type: ignore
                self.session.add(oauth_account)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def update(self, user: UD) -> UD:
        """Update a user."""
        self.session.add(user)
        if self.oauth_account_model is not None:
            for oauth_account in user.oauth_accounts:  # type: ignore
                self.session.add(oauth_account)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def delete(self, user: UD) -> None:
        """Delete a user."""
        self.session.delete(user)
        self.session.commit()


class SQLModelUserDatabaseAsync(Generic[UD, OA], BaseUserDatabase[UD]):
    """
    Database adapter for SQLModel working purely asynchronously.

    :param user_db_model: SQLModel model of a DB representation of a user.
    :param session: SQLAlchemy async session.
    """

    session: AsyncSession
    oauth_account_model: Optional[Type[OA]]

    def __init__(
        self,
        user_db_model: Type[UD],
        session: AsyncSession,
        oauth_account_model: Optional[Type[OA]] = None,
    ):
        super().__init__(user_db_model)
        self.session = session
        self.oauth_account_model = oauth_account_model

    async def get(self, id: UUID4) -> Optional[UD]:
        """Get a single user by id."""
        return await self.session.get(self.user_db_model, id)

    async def get_by_email(self, email: str) -> Optional[UD]:
        """Get a single user by email."""
        statement = select(self.user_db_model).where(
            func.lower(self.user_db_model.email) == func.lower(email)
        )
        results = await self.session.execute(statement)
        object = results.first()
        if object is None:
            return None
        return object[0]

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UD]:
        """Get a single user by OAuth account id."""
        if not self.oauth_account_model:
            raise NotSetOAuthAccountTableError()
        statement = (
            select(self.oauth_account_model)
            .where(self.oauth_account_model.oauth_name == oauth)
            .where(self.oauth_account_model.account_id == account_id)
            .options(selectinload(self.oauth_account_model.user))  # type: ignore
        )
        results = await self.session.execute(statement)
        oauth_account = results.first()
        if oauth_account:
            user = oauth_account[0].user
            return user
        return None

    async def create(self, user: UD) -> UD:
        """Create a user."""
        self.session.add(user)
        if self.oauth_account_model is not None:
            for oauth_account in user.oauth_accounts:  # type: ignore
                self.session.add(oauth_account)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: UD) -> UD:
        """Update a user."""
        self.session.add(user)
        if self.oauth_account_model is not None:
            for oauth_account in user.oauth_accounts:  # type: ignore
                self.session.add(oauth_account)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: UD) -> None:
        """Delete a user."""
        await self.session.delete(user)
        await self.session.commit()
