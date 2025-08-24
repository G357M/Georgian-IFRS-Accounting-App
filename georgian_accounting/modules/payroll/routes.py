from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from georgian_accounting.utils.decorators import permission_required
from .models import Employee
from georgian_accounting.database import db
from datetime import datetime
from decimal import Decimal

payroll_bp = Blueprint(
    'payroll', 
    __name__, 
    template_folder='templates',
    url_prefix='/payroll'
)

@payroll_bp.route('/')
@login_required
@permission_required('view_payroll')
def index():
    return render_template('payroll_dashboard.html')

@payroll_bp.route('/employees')
@login_required
@permission_required('view_payroll')
def list_employees():
    employees = Employee.query.order_by(Employee.last_name, Employee.first_name).all()
    return render_template('employees.html', employees=employees)

@payroll_bp.route('/employee/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_payroll')
def add_employee():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        personal_id = request.form.get('personal_id')
        hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d')
        salary = Decimal(request.form.get('salary'))
        is_active = 'is_active' in request.form
        in_pension_scheme = 'in_pension_scheme' in request.form

        if Employee.query.filter_by(personal_id=personal_id).first():
            flash('Employee with this Personal ID already exists.', 'danger')
        else:
            new_employee = Employee(
                first_name=first_name,
                last_name=last_name,
                personal_id=personal_id,
                hire_date=hire_date,
                salary=salary,
                is_active=is_active,
                in_pension_scheme=in_pension_scheme
            )
            db.session.add(new_employee)
            db.session.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('payroll.list_employees'))
            
    return render_template('employee_form.html', action="Add")

@payroll_bp.route('/periods')
@login_required
@permission_required('view_payroll')
def list_periods():
    # Will be implemented later
    return "<h1>List of Payroll Periods</h1>"

@payroll_bp.route('/payslips')
@login_required
@permission_required('view_payroll')
def list_payslips():
    # Will be implemented later
    return "<h1>List of Payslips</h1>"
