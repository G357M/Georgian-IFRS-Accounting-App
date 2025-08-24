import uuid
from datetime import datetime
from decimal import Decimal
from georgian_accounting.database import db

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    unit_of_measure = db.Column(db.String(20))
    is_vat_exempt = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inventory_transactions = db.relationship('InventoryTransaction', back_populates='product')

    def __repr__(self):
        return f'<Product {self.code} - {self.name}>'

class InventoryTransaction(db.Model):
    __tablename__ = 'inventory_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Numeric(15, 2), nullable=False)
    reference_document = db.Column(db.String(100))
    status = db.Column(db.String(20), default='draft') # draft, posted, voided
    transaction_type = db.Column(db.String(50), nullable=False) # 'receipt', 'issue', 'adjustment'

    __mapper_args__ = {
        'polymorphic_identity': 'inventory_transaction',
        'polymorphic_on': transaction_type
    }

    product = db.relationship('Product', back_populates='inventory_transactions')

    def __repr__(self):
        return f'<InventoryTransaction {self.transaction_uuid} - {self.transaction_type}>'

class StockReceipt(InventoryTransaction):
    __tablename__ = 'stock_receipts'
    id = db.Column(db.Integer, db.ForeignKey('inventory_transactions.id'), primary_key=True)
    unit_cost = db.Column(db.Numeric(15, 2), nullable=False)
    supplier = db.Column(db.String(100))
    purchase_invoice_id = db.Column(db.Integer) # Placeholder for future Invoice relationship

    __mapper_args__ = {
        'polymorphic_identity': 'receipt',
    }

class StockIssue(InventoryTransaction):
    __tablename__ = 'stock_issues'
    id = db.Column(db.Integer, db.ForeignKey('inventory_transactions.id'), primary_key=True)
    customer = db.Column(db.String(100))
    sales_invoice_id = db.Column(db.Integer) # Placeholder for future Invoice relationship

    __mapper_args__ = {
        'polymorphic_identity': 'issue',
    }

class InventoryAdjustment(InventoryTransaction):
    __tablename__ = 'inventory_adjustments'
    id = db.Column(db.Integer, db.ForeignKey('inventory_transactions.id'), primary_key=True)
    reason = db.Column(db.String(255))
    approved_by = db.Column(db.String(100)) # Placeholder for User relationship

    __mapper_args__ = {
        'polymorphic_identity': 'adjustment',
    }
