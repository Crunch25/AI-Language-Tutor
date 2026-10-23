from fastapi import APIRouter
from backend.app.api.v1.endpoints import users
from backend.app.api.v1.endpoints import auth, chat

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(chat.router)