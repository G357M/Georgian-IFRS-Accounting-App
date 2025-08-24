from flask import Blueprint, render_template
from flask_login import login_required
from georgian_accounting.modules.audit.models import AuditTrail
from georgian_accounting.modules.auth.models import User
from georgian_accounting.utils.decorators import permission_required

reporting_bp = Blueprint(
    'reporting', 
    __name__, 
    template_folder='templates',
    url_prefix='/reporting'
)

@reporting_bp.route('/')
@login_required
@permission_required('view_reports')
def index():
    return render_template('reporting_dashboard.html')

@reporting_bp.route('/audit-log')
@login_required
@permission_required('view_audit_log')
def audit_log():
    audit_entries = AuditTrail.query.order_by(AuditTrail.timestamp.desc()).limit(100).all()
    return render_template('audit_log_report.html', audit_entries=audit_entries)