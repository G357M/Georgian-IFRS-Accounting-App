from enum import Enum
from dataclasses import dataclass
from typing import Set, List
from functools import wraps
from fastapi import Depends, HTTPException, status

# This would be part of a user module, but is placed here for simplicity.
# from .jwt_handler import jwt_handler, TokenData
# from fastapi.security import OAuth2PasswordBearer

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Permission(str, Enum):
    ACCOUNTS_READ = "accounts:read"
    ACCOUNTS_WRITE = "accounts:write"
    TRANSACTIONS_READ = "transactions:read"
    TRANSACTIONS_WRITE = "transactions:write"
    TRANSACTIONS_APPROVE = "transactions:approve"
    REPORTS_FINANCIAL = "reports:financial"
    REPORTS_TAX = "reports:tax"
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"

@dataclass
class Role:
    name: str
    permissions: Set[Permission]

class GeorgianAccountingRoles:
    ACCOUNTANT = Role("accountant", {
        Permission.ACCOUNTS_READ,
        Permission.TRANSACTIONS_READ,
        Permission.TRANSACTIONS_WRITE,
        Permission.REPORTS_FINANCIAL
    })
    
    CHIEF_ACCOUNTANT = Role("chief_accountant", {
        *ACCOUNTANT.permissions,
        Permission.ACCOUNTS_WRITE,
        Permission.TRANSACTIONS_APPROVE,
        Permission.REPORTS_TAX,
        Permission.ADMIN_USERS
    })
    
    TAX_SPECIALIST = Role("tax_specialist", {
        Permission.ACCOUNTS_READ,
        Permission.TRANSACTIONS_READ,
        Permission.REPORTS_TAX
    })

    ADMIN = Role("admin", {p for p in Permission}) # Admin has all permissions

# --- Placeholder User Model ---
@dataclass
class User:
    id: str
    username: str
    permissions: List[Permission]

# --- Placeholder Dependency for getting current user ---
# In a real app, this would decode the JWT from the Authorization header
async def get_current_user() -> User:
    # This is a mock user for demonstration.
    # A real implementation would look like this:
    #
    # async def get_current_user(token: str = Depends(oauth2_scheme)):
    #     try:
    #         payload = jwt_handler.decode_token(token)
    #         token_data = TokenData(**payload)
    #         # Fetch user from DB based on token_data.sub
    #         user = await user_repository.get_by_id(token_data.sub)
    #         if not user:
    #             raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    #         return User(id=user.id, username=user.username, permissions=user.permissions)
    #     except ValueError:
    #         raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    
    return User(id="user-123", username="mockuser", permissions=[
        Permission.ACCOUNTS_READ,
        Permission.TRANSACTIONS_READ,
        Permission.TRANSACTIONS_WRITE,
    ])


# --- Dependency for checking permissions ---
def require_permission(permission: Permission):
    """
    FastAPI dependency that checks if the current user has the required permission.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
            if permission not in current_user.permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# Example usage in a FastAPI route:
#
# @app.post("/api/v1/transactions")
# @require_permission(Permission.TRANSACTIONS_WRITE)
# async def create_transaction(transaction: TransactionCreate, current_user: User = Depends(get_current_user)):
#     # The code here will only execute if the user has the 'transactions:write' permission.
#     return await transaction_service.create(transaction, performed_by=current_user)
