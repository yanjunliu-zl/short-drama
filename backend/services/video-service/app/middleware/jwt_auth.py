"""JWT 认证中间件"""
import re
from typing import Optional
from fastapi import Request, HTTPException, Header
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.core.config import settings


# 跳过认证的路径
SKIP_AUTH_PATHS = [
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/docs",
    "/openapi.json",
    "/redoc",
]


def create_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """验证 JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


async def jwt_auth_middleware(request: Request, authorization: Optional[str] = Header(None)) -> None:
    """JWT 认证中间件"""
    # 检查是否跳过认证
    for path in SKIP_AUTH_PATHS:
        if request.url.path.startswith(path):
            return

    # 检查 Authorization 头
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # 验证 token 格式
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 将用户信息添加到请求状态
    request.state.user_id = payload.get("sub")
    request.state.token = token
