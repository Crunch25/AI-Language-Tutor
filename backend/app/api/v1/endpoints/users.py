from fastapi import APIRouter, status

from app.api.deps import CurrentUser
from app.core.unit_of_work import UOWDep
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile",
)
async def get_my_profile(current_user: CurrentUser) -> UserRead:
    """Retrieves profile information for the authenticated user."""
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated user profile",
)
async def update_my_profile(
    payload: UserUpdate,
    current_user: CurrentUser,
    uow: UOWDep,
) -> UserRead:
    """Updates language preferences or display name for the authenticated user."""
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await uow.user_repo.add(current_user)
    await uow.commit()

    return UserRead.model_validate(current_user)