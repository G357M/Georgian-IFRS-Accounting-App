from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from .models import Employee
from georgian_accounting.database import db
from georgian_accounting.utils.decorators import permission_required
from .forms import EmployeeForm, DeleteForm 

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
    delete_form = DeleteForm()  # For CSRF protection on delete buttons
    return render_template('employees.html', employees=employees, delete_form=delete_form)

@payroll_bp.route('/employee/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_payroll')
def add_employee():
    form = EmployeeForm()
    if form.validate_on_submit():
        new_employee = Employee()
        form.populate_obj(new_employee)
        db.session.add(new_employee)
        db.session.commit()
        flash('Employee added successfully!', 'success')
        return redirect(url_for('payroll.list_employees'))
    return render_template('employee_form.html', form=form, action="Add")

@payroll_bp.route('/employee/edit/<int:employee_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_payroll')
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    form = EmployeeForm(obj=employee, original_personal_id=employee.personal_id)
    if form.validate_on_submit():
        form.populate_obj(employee)
        db.session.commit()
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('payroll.list_employees'))
    return render_template('employee_form.html', form=form, action="Edit")

@payroll_bp.route('/employee/delete/<int:employee_id>', methods=['POST'])
@login_required
@permission_required('manage_payroll')
def delete_employee(employee_id):
    form = DeleteForm()
    if form.validate_on_submit(): # This validates the CSRF token
        employee = Employee.query.get_or_404(employee_id)
        try:
            db.session.delete(employee)
            db.session.commit()
            flash('Employee deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting employee. They might be associated with payrolls. Error: {e}', 'danger')
    else:
        flash('Invalid request. Could not delete employee.', 'danger')
    return redirect(url_for('payroll.list_employees'))

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
