from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
import structlog

from new_system.auth.jwt_handler import jwt_handler, TokenPair
from new_system.auth.rbac import User, get_current_user, Permission, require_permission

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup sequence initiated.")
    yield
    logger.info("Application shutdown sequence initiated.")

app = FastAPI(
    title="Georgian Accounting System v2.0",
    description="Modern IFRS-compliant accounting system",
    version="2.0.0",
    lifespan=lifespan
)

# --- Authentication Endpoint ---
@app.post("/api/v1/auth/token", response_model=TokenPair, tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # In a real app, you would verify username and password against the database
    if form_data.username == "testuser" and form_data.password == "testpass":
        # For demonstration, we'll grant a mock user with specific permissions
        user_id = "user-123"
        permissions = [Permission.ACCOUNTS_READ, Permission.TRANSACTIONS_READ]
        tokens = await jwt_handler.create_tokens(user_id, [p.value for p in permissions])
        return tokens
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

# --- Protected Endpoint Example ---
@app.get("/api/v1/secure-data", tags=["Testing"])
@require_permission(Permission.ACCOUNTS_READ)
async def get_secure_data(current_user: User = Depends(get_current_user)):
    return {"message": "This is secure data", "user": current_user}


@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Check the health of the service."""
    return {"status": "ok"}

# Placeholder for routes
@app.get("/api/v1/accounts", tags=["Accounts"])
async def get_accounts():
    return {"message": "List of accounts"}

@app.get("/api/v1/transactions", tags=["Transactions"])
async def get_transactions():
    return {"message": "List of transactions"}

@app.get("/api/v1/reports", tags=["Reports"])
async def get_reports():
    return {"message": "List of reports"}
