import uuid
from datetime import datetime
from decimal import Decimal
from georgian_accounting.database import db

class Account(db.Model):
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(20), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='GEL')
    is_active = db.Column(db.Boolean, default=True)
    balance = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    
    entries = db.relationship('JournalEntry', back_populates='account')

    def __repr__(self):
        return f'<Account {self.code} - {self.name}>'

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=False)
    reference = db.Column(db.String(100))
    status = db.Column(db.String(20), default='draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entries = db.relationship('JournalEntry', back_populates='transaction', cascade="all, delete-orphan")

    def validate(self):
        total_debits = sum(entry.debit for entry in self.entries)
        total_credits = sum(entry.credit for entry in self.entries)
        return total_debits == total_credits

    def __repr__(self):
        return f'<Transaction {self.transaction_uuid} on {self.date}>'

class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    debit = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    credit = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    currency = db.Column(db.String(3), nullable=False, default='GEL')
    exchange_rate = db.Column(db.Numeric(15, 5), default=Decimal('1.00000'))

    transaction = db.relationship('Transaction', back_populates='entries')
    account = db.relationship('Account', back_populates='entries')

    def __repr__(self):
        return f'<JournalEntry {self.id} Dr:{self.debit} Cr:{self.credit}>'

class FinancialStatement(db.Model):
    __tablename__ = 'financial_statements'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    statement_type = db.Column(db.String(50), nullable=False) # e.g., 'BalanceSheet', 'IncomeStatement'
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.Column(db.Text) 

    company = db.relationship('Company', backref='financial_statements')

    __mapper_args__ = {
        'polymorphic_identity': 'financial_statement',
        'polymorphic_on': statement_type
    }

    def __repr__(self):
        return f'<FinancialStatement {self.statement_type} for {self.company.name} ({self.period_start.strftime("%Y-%m-%d")})>'

class BalanceSheet(FinancialStatement):
    __tablename__ = 'balance_sheets'
    id = db.Column(db.Integer, db.ForeignKey('financial_statements.id'), primary_key=True)
    __mapper_args__ = {
        'polymorphic_identity': 'BalanceSheet',
    }

class IncomeStatement(FinancialStatement):
    __tablename__ = 'income_statements'
    id = db.Column(db.Integer, db.ForeignKey('financial_statements.id'), primary_key=True)
    __mapper_args__ = {
        'polymorphic_identity': 'IncomeStatement',
    }