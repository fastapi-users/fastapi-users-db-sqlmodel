"""FastAPI Users database adapter for SQLModel."""
import uuid
from typing import Generic, Optional, Type, TypeVar

from fastapi_users.db.base import BaseUserDatabase
from fastapi_users.models import BaseOAuthAccount, BaseUserDB
from pydantic import UUID4, EmailStr
from sqlalchemy.future import Engine
from sqlmodel import Field, Session, SQLModel, func, select

__version__ = "0.0.1"


class SQLModelBaseUserDB(BaseUserDB, SQLModel):
    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(sa_column_kwargs={"unique": True, "index": True})

    class Config:
        orm_mode = True


class SQLModelBaseOAuthAccount(BaseOAuthAccount, SQLModel):
    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True)

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
    :param engine: SQLAlchemy engine.
    """

    engine: Engine
    oauth_account_model: Optional[Type[OA]]

    def __init__(
        self,
        user_db_model: Type[UD],
        engine: Engine,
        oauth_account_model: Optional[Type[OA]] = None,
    ):
        super().__init__(user_db_model)
        self.engine = engine
        self.oauth_account_model = oauth_account_model

    async def get(self, id: UUID4) -> Optional[UD]:
        """Get a single user by id."""
        with Session(self.engine) as session:
            return session.get(self.user_db_model, id)

    async def get_by_email(self, email: str) -> Optional[UD]:
        """Get a single user by email."""
        with Session(self.engine) as session:
            statement = select(self.user_db_model).where(
                func.lower(self.user_db_model.email) == func.lower(email)
            )
            results = session.exec(statement)
            return results.first()

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UD]:
        """Get a single user by OAuth account id."""
        if not self.oauth_account_model:
            raise NotSetOAuthAccountTableError()
        with Session(self.engine) as session:
            statement = (
                select(self.oauth_account_model)
                .where(self.oauth_account_model.oauth_name == oauth)
                .where(self.oauth_account_model.account_id == account_id)
            )
            results = session.exec(statement)
            oauth_account = results.first()
            if oauth_account:
                user = oauth_account.user  # type: ignore
                return user
            return None

    async def create(self, user: UD) -> UD:
        """Create a user."""
        with Session(self.engine) as session:
            session.add(user)
            if self.oauth_account_model is not None:
                for oauth_account in user.oauth_accounts:  # type: ignore
                    session.add(oauth_account)
            session.commit()
            session.refresh(user)
            return user

    async def update(self, user: UD) -> UD:
        """Update a user."""
        with Session(self.engine) as session:
            session.add(user)
            if self.oauth_account_model is not None:
                for oauth_account in user.oauth_accounts:  # type: ignore
                    session.add(oauth_account)
            session.commit()
            session.refresh(user)
            return user

    async def delete(self, user: UD) -> None:
        """Delete a user."""
        with Session(self.engine) as session:
            session.delete(user)
            session.commit()
