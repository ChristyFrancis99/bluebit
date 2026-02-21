from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from services.auth import get_current_user, TokenData

# Re-export for convenience
DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
