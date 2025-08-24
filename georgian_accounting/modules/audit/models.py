import uuid
from datetime import datetime
from georgian_accounting.database import db

class AuditTrail(db.Model):
    __tablename__ = 'audit_trails'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(36))
    action = db.Column(db.String(20), nullable=False) # create, update, delete
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    changes = db.Column(db.JSON)

    user = db.relationship('User')

    def __repr__(self):
        return f'<AuditTrail {self.timestamp} - {self.user.username if self.user else "System"} {self.action} {self.entity_type}>'
