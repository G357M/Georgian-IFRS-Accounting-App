import uuid
from datetime import datetime
from decimal import Decimal
from georgian_accounting.database import db

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
    
    total_net = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    total_vat = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    total_gross = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))

    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)

    customer = db.relationship('Customer', back_populates='invoices')
    vendor = db.relationship('Vendor', back_populates='invoices')
    items = db.relationship('InvoiceItem', back_populates='invoice', cascade="all, delete-orphan")

    def recalculate_totals(self):
        self.total_net = sum(item.net_amount for item in self.items)
        self.total_vat = sum(item.vat_amount for item in self.items)
        self.total_gross = self.total_net + self.total_vat

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(15, 2), default=Decimal('1.00'))
    unit_price = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    vat_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.18'))
    
    net_amount = db.Column(db.Numeric(15, 2))
    vat_amount = db.Column(db.Numeric(15, 2))

    invoice = db.relationship('Invoice', back_populates='items')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.net_amount = self.quantity * self.unit_price
        self.vat_amount = self.net_amount * self.vat_rate
