from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.user_repository import UserRepository
from app.database.repositories.company_repository import CompanyRepository
from app.dependencies import get_db, get_current_user
from app.schemas import user as user_schema
from app.schemas import token as token_schema
from app.services import auth_service
from app.database.models import user as user_model

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=user_schema.UserRegistrationResponse)
async def register_user(
    user_in: user_schema.UserCreate, db: AsyncSession = Depends(get_db)
):
    user_repo = UserRepository(db)
    company_repo = CompanyRepository(db)

    # Проверяем, что пользователь еще не зарегистрирован
    db_user = await user_repo.get_user_by_email(email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Создаем пользователя
    new_user = await user_repo.create_user(user=user_in)

    # Автоматически создаем компанию для пользователя
    company_created = False
    try:
        new_company = await company_repo.create_default_company(
            user_id=new_user.id, user_email=new_user.email
        )

        # Устанавливаем созданную компанию как текущую
        new_user.current_company_id = new_company.id
        await company_repo.db.commit()

        company_created = True
    except Exception as e:
        # Если создание компании не удалось, логируем ошибку
        # но не прерываем регистрацию пользователя
        import logging

        logging.error(
            f"Failed to create default company for user {new_user.email}: {str(e)}"
        )

    return user_schema.UserRegistrationResponse(
        user=new_user,
        company_created=company_created,
        message=(
            "Пользователь успешно зарегистрирован. Компания создана автоматически."
            if company_created
            else "Пользователь зарегистрирован, но не удалось создать компанию. Обратитесь к администратору."
        ),
        setup_required=(
            "Необходимо настроить интеграцию с Яндекс.Метрикой в разделе 'Компании'"
            if company_created
            else "Обратитесь к администратору для создания компании."
        ),
    )


@router.post("/login", response_model=token_schema.Token)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_email(email=form_data.username)
    if not user or not auth_service.verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=user_schema.User)
async def get_current_user_info(
    current_user: user_model.User = Depends(get_current_user),
):
    """Получение информации о текущем пользователе"""
    return current_user
