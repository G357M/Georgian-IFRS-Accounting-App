import uuid
from datetime import datetime
from decimal import Decimal
from georgian_accounting.database import db

class TaxRate(db.Model):
    __tablename__ = 'tax_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    tax_type = db.Column(db.String(50), nullable=False) # VAT, income_tax, etc.
    rate = db.Column(db.Numeric(5, 4), nullable=False) # e.g., 0.18 for 18%
    effective_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime) # Null if current
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TaxRate {self.tax_type} {self.rate*100:.2f}% from {self.effective_date.strftime("%Y-%m-%d")}>'

class VATDeclaration(db.Model):
    __tablename__ = 'vat_declarations'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    vat_payable = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    vat_receivable = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    net_vat = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    status = db.Column(db.String(20), default='draft') # draft, submitted, paid
    submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref='vat_declarations')

    def __repr__(self):
        return f'<VATDeclaration {self.period_start.strftime("%Y-%m")} for {self.company.name}>'

class IncomeTaxDeclaration(db.Model):
    __tablename__ = 'income_tax_declarations'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    taxable_income = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    tax_amount = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    status = db.Column(db.String(20), default='draft')
    submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref='income_tax_declarations')

    def __repr__(self):
        return f'<IncomeTaxDeclaration {self.year} for {self.company.name}>'

class PensionContribution(db.Model):
    __tablename__ = 'pension_contributions'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    payroll_period_id = db.Column(db.Integer, db.ForeignKey('payroll_periods.id'), nullable=False)
    employee_contribution = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    employer_contribution = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    government_contribution = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref='pension_contributions')
    payroll_period = db.relationship('PayrollPeriod', backref='pension_contributions')

    def __repr__(self):
        return f'<PensionContribution for Employee {self.employee_id} in Period {self.payroll_period_id}>'

class TaxCalendar(db.Model):
    __tablename__ = 'tax_calendar'
    
    id = db.Column(db.Integer, primary_key=True)
    tax_type = db.Column(db.String(50), nullable=False)
    deadline_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TaxCalendar {self.tax_type} {self.deadline_date.strftime("%Y-%m-%d")}>'
