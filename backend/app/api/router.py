from fastapi import APIRouter

from app.api.v1.endpoints import auth, config, health, terminals
# from app.api.v1.endpoints import users  # EICN 납품: 가입자 승인 관리 비활성화

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
# EICN 납품: 가입자 승인 관리 API 비활성화.
# api_router.include_router(users.router)
api_router.include_router(config.router)
api_router.include_router(terminals.router)
