import uuid
from datetime import datetime
from decimal import Decimal
from georgian_accounting.database import db

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    personal_id = db.Column(db.String(20), unique=True, nullable=False) # Georgian ID number
    hire_date = db.Column(db.DateTime, nullable=False)
    termination_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    salary = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    salary_currency = db.Column(db.String(3), nullable=False, default='GEL')
    in_pension_scheme = db.Column(db.Boolean, default=True) # Georgian pension participation
    
    # Optional fields
    birth_date = db.Column(db.DateTime)
    gender = db.Column(db.String(1))
    department = db.Column(db.String(50))
    position = db.Column(db.String(50))
    bank_account = db.Column(db.String(50))
    bank_code = db.Column(db.String(20))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))

    payslips = db.relationship('Payslip', back_populates='employee')

    def __repr__(self):
        return f'<Employee {self.first_name} {self.last_name}>'

class PayrollPeriod(db.Model):
    __tablename__ = 'payroll_periods'
    
    id = db.Column(db.Integer, primary_key=True)
    period_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='open') # open, calculated, approved, paid

    payslips = db.relationship('Payslip', back_populates='payroll_period')

    def __repr__(self):
        return f'<PayrollPeriod {self.start_date.strftime("%Y-%m-%d")} to {self.end_date.strftime("%Y-%m-%d")}>'

class Payslip(db.Model):
    __tablename__ = 'payslips'
    
    id = db.Column(db.Integer, primary_key=True)
    payslip_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    payroll_period_id = db.Column(db.Integer, db.ForeignKey('payroll_periods.id'), nullable=False)
    
    gross_salary = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    income_tax = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    pension_contribution_employee = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    pension_contribution_employer = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    pension_contribution_government = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    net_salary = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    
    # Additional earnings or deductions (can be stored as JSON or separate table)
    items = db.Column(db.JSON) 

    employee = db.relationship('Employee', back_populates='payslips')
    payroll_period = db.relationship('PayrollPeriod', back_populates='payslips')

    def __repr__(self):
        return f'<Payslip {self.payslip_uuid} for {self.employee.first_name}>'
