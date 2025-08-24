from functools import wraps
from flask import abort
from flask_login import current_user

def permission_required(permission):
    """
    Decorator to restrict access to a route based on user permissions.
    Usage:
    @permission_required('manage_users')
    def some_admin_route():
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401) # Unauthorized
            if not current_user.has_permission(permission):
                abort(403) # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator
