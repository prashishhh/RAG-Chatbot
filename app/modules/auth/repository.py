from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken, User


class AuthRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def update_last_login(self, user: User, logged_in_at: datetime) -> User:
        user.last_login_at = logged_in_at
        await self.db.flush()
        return user

    async def create_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self.db.add(refresh_token)
        await self.db.flush()
        return refresh_token

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self,
        refresh_token: RefreshToken,
        revoked_at: datetime,
        replaced_by_token_id: UUID | None = None,
    ) -> RefreshToken:
        refresh_token.revoked_at = revoked_at
        refresh_token.replaced_by_token_id = replaced_by_token_id
        await self.db.flush()
        return refresh_token

    async def revoke_all_user_refresh_tokens(self, user_id: UUID, revoked_at: datetime) -> int:
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        return result.rowcount or 0

