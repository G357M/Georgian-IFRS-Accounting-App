from datetime import datetime
from georgian_accounting.database import db

class Company(db.Model):
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    registration_number = db.Column(db.String(50), unique=True)
    tax_id = db.Column(db.String(50), unique=True)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Company {self.name}>'

class FiscalPeriod(db.Model):
    __tablename__ = 'fiscal_periods'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    period_name = db.Column(db.String(50), nullable=False) # e.g., "Q1 2024", "FY 2024"
    is_open = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref='fiscal_periods')

    def __repr__(self):
        return f'<FiscalPeriod {self.period_name} ({self.start_date.strftime("%Y")})>'
