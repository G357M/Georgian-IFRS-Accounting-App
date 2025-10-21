import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Any

from jose import JWTError, jwt

# In a real app, load this from config/environment variables
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

class TokenPair:
    def __init__(self, access_token: str, refresh_token: str, expires_in: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = "bearer"
        self.expires_in = expires_in

class JWTHandler:
    def __init__(self, secret_key: str, algorithm: str):
        self.secret_key = secret_key
        self.algorithm = algorithm
        # In a real app, you would have a Redis client here for refresh token storage
        # self.redis = redis.Redis()

    async def create_tokens(self, user_id: str, permissions: List[str]) -> TokenPair:
        """
        Creates both access and refresh tokens for a user.
        """
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        access_payload = {
            "sub": user_id,
            "permissions": permissions,
            "type": "access",
            "exp": datetime.utcnow() + access_token_expires,
            "iat": datetime.utcnow(),
            "jti": secrets.token_hex(16)  # Unique ID for the token
        }
        
        refresh_payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + refresh_token_expires,
            "iat": datetime.utcnow(),
            "jti": secrets.token_hex(16)
        }
        
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
        
        # Store the refresh token's jti in a persistent store (e.g., Redis) to allow for revocation
        # await self.redis.setex(f"refresh:{refresh_payload['jti']}", 
        #                       int(refresh_token_expires.total_seconds()),
        #                       user_id)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_token_expires.total_seconds())
        )

    async def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decodes a JWT token.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            # You can log the error or handle different error types
            raise ValueError(f"Invalid token: {e}")

# Instantiate the handler for use in the application
jwt_handler = JWTHandler(secret_key=SECRET_KEY, algorithm=ALGORITHM)
