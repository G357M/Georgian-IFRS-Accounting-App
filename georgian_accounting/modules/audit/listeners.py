from sqlalchemy import event
from flask_login import current_user
from georgian_accounting.database import db
from .models import AuditTrail

def get_model_changes(model):
    """Return a dictionary of changes for a model instance."""
    state = db.inspect(model)
    changes = {}
    for attr in state.attrs:
        hist = state.get_history(attr.key, True)
        if hist.has_changes():
            old_value = hist.deleted[0] if hist.deleted else None
            new_value = hist.added[0] if hist.added else None
            # For many-to-many or one-to-many, the values can be objects
            # Here we just convert to string for simplicity in audit log
            if hasattr(old_value, 'id'): old_value = str(old_value.id)
            if hasattr(new_value, 'id'): new_value = str(new_value.id)
            changes[attr.key] = {'old': old_value, 'new': new_value}
    return changes

@event.listens_for(db.session, 'before_flush')
def before_flush(session, flush_context, instances):
    """Listen for changes before they are committed to the database."""
    user_id = current_user.id if current_user and current_user.is_authenticated else None

    for obj in session.new:
        if not isinstance(obj, AuditTrail):
            changes = get_model_changes(obj)
            if changes:
                audit = AuditTrail(
                    user_id=user_id,
                    entity_type=obj.__tablename__,
                    action='create',
                    changes=changes
                )
                session.add(audit)

    for obj in session.dirty:
        if not isinstance(obj, AuditTrail):
            changes = get_model_changes(obj)
            if changes:
                # The ID might not be loaded in the instance yet, so we get it from state
                identity = db.inspect(obj).identity
                entity_id = str(identity[0]) if identity else None
                audit = AuditTrail(
                    user_id=user_id,
                    entity_type=obj.__tablename__,
                    entity_id=entity_id,
                    action='update',
                    changes=changes
                )
                session.add(audit)

    for obj in session.deleted:
        if not isinstance(obj, AuditTrail):
            changes = get_model_changes(obj)
            identity = db.inspect(obj).identity
            entity_id = str(identity[0]) if identity else None
            audit = AuditTrail(
                user_id=user_id,
                entity_type=obj.__tablename__,
                entity_id=entity_id,
                action='delete',
                changes=changes
            )
            session.add(audit)
