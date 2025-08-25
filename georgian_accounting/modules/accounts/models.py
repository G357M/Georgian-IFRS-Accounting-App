import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.hybrid import hybrid_property
from georgian_accounting.database import db

class AccountType(db.Model):
    __tablename__ = 'account_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # e.g., 'Asset', 'Liability', 'Equity', 'Revenue', 'Expense'
    description = db.Column(db.Text)
    accounts = db.relationship('Account', back_populates='account_type_rel', lazy=True)

class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(50), unique=True, nullable=False)
    account_name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign key for hierarchical accounts
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    children = db.relationship('Account', backref=db.backref('parent', remote_side=[id]), lazy=True)

    # Foreign key for account type
    account_type_id = db.Column(db.Integer, db.ForeignKey('account_types.id'), nullable=False)
    account_type_rel = db.relationship('AccountType', back_populates='accounts')

    def __repr__(self):
        return f'<Account {self.account_number} - {self.account_name}>'

class Party(db.Model):
    """Abstract base for Customer and Vendor."""
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    tax_id = db.Column(db.String(20), unique=True)
    is_foreign = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Customer(Party):
    __tablename__ = 'customers'
    invoices = db.relationship('Invoice', back_populates='customer')

class Vendor(Party):
    __tablename__ = 'vendors'
    invoices = db.relationship('Invoice', back_populates='vendor')

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    invoice_number = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    currency = db.Column(db.String(3), nullable=False, default='GEL')
    status = db.Column(db.String(20), default='draft') # draft, issued, paid, cancelled
    
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)

    customer = db.relationship('Customer', back_populates='invoices')
    vendor = db.relationship('Vendor', back_populates='invoices')
    items = db.relationship('InvoiceItem', back_populates='invoice', cascade="all, delete-orphan", lazy="dynamic")

    @hybrid_property
    def total_net(self):
        return sum(item.net_amount for item in self.items) if self.items else Decimal('0.00')

    @hybrid_property
    def total_vat(self):
        return sum(item.vat_amount for item in self.items) if self.items else Decimal('0.00')

    @hybrid_property
    def total_gross(self):
        return self.total_net + self.total_vat

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(15, 2), default=Decimal('1.00'), nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), default=Decimal('0.00'), nullable=False)
    vat_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.18'), nullable=False)

    invoice = db.relationship('Invoice', back_populates='items')

    @hybrid_property
    def net_amount(self):
        return self.quantity * self.unit_price

    @hybrid_property
    def vat_amount(self):
        return self.net_amount * self.vat_rate