from georgian_accounting.database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from georgian_accounting.config import Config

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(64), default='Accountant') # Roles: Administrator, Chief Accountant, Accountant, etc.

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission):
        """Check if the user's role has the given permission."""
        role_permissions = Config.ROLES_PERMISSIONS.get(self.role, [])
        return permission in role_permissions

    def __repr__(self):
        return f'<User {self.username}>'