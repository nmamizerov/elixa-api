from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.database.models.user import User
from app.schemas.user import User as UserSchema

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserSchema)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
