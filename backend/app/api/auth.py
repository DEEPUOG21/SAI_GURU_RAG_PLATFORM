import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.database.session import bind_scope, get_db
from app.models.entities import Tenant, User, new_id
from app.schemas.requests import LoginRequest, SignupRequest, UserRequest
from app.schemas.responses import ProfileResponse, TokenResponse, UserResponse
from app.security.auth import create_token, current_scope, passwords, rate_limit, require_role

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
DUMMY_HASH = passwords.hash("not-a-real-user-password")


@router.post("/signup", status_code=201, response_model=TokenResponse)
async def signup(body: SignupRequest, request: Request, db=Depends(get_db)):
    await rate_limit(db, "signup:" + (request.client.host if request.client else "unknown"), 5)
    # Registration creates a fresh tenant. Client-supplied roles and tenant IDs are forbidden.
    tenant = Tenant(id=new_id(), name=body.workspace_name)
    user = User(
        id=new_id(),
        tenant_id=tenant.id,
        email=body.email.lower(),
        role="ADMIN",
        token_version=0,
        password_hash=await asyncio.to_thread(passwords.hash, body.password),
    )
    await bind_scope(db, tenant_id=tenant.id, user_id=user.id)
    try:
        db.add(tenant)
        await db.flush()
        db.add(user)
        await db.flush()
        token = create_token(user)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "An account with this email already exists. Sign in instead.") from exc
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db=Depends(get_db)):
    await rate_limit(db, "login:" + (request.client.host if request.client else "unknown"), 10)
    await bind_scope(db, login_email=body.email.lower())
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    valid = await asyncio.to_thread(
        passwords.verify, body.password, user.password_hash if user else DUMMY_HASH
    )
    if not user or not valid:
        raise HTTPException(401, "Incorrect email or password.")
    return {"access_token": create_token(user), "token_type": "bearer", "expires_in": 3600}


@router.get("/me", response_model=ProfileResponse)
async def me(scope=Depends(current_scope), db=Depends(get_db)):
    user, tenant = await db.get(User, scope.user_id), await db.get(Tenant, scope.tenant_id)
    return {"id": user.id, "email": user.email, "role": user.role, "tenant": tenant.name}


@router.post("/logout", status_code=204)
async def logout(scope=Depends(current_scope), db=Depends(get_db)):
    """Revoke every existing token for this account, including copied tokens."""
    await db.execute(
        update(User).where(User.id == scope.user_id).values(token_version=User.token_version + 1)
    )
    await db.commit()


@router.post("/users", status_code=201, response_model=UserResponse)
async def add_user(body: UserRequest, scope=Depends(current_scope), db=Depends(get_db)):
    require_role(scope, 2)
    user = User(
        tenant_id=scope.tenant_id,
        email=body.email.lower(),
        role=body.role,
        password_hash=await asyncio.to_thread(passwords.hash, body.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from exc
    return {"id": user.id, "email": user.email, "role": user.role}
