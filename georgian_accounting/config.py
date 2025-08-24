# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Basic configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'georgian_accounting.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Georgian specific settings
    DEFAULT_CURRENCY = 'GEL'
    VAT_RATE = 0.18  # 18% VAT in Georgia
    PENSION_CONTRIBUTION_RATE = 0.02  # 2% contribution
    LANGUAGE = 'ka'  # Georgian language code
    
    # IFRS specific settings
    FISCAL_YEAR_START = '01-01'  # January 1st
    FISCAL_YEAR_END = '12-31'  # December 31st
    
    # File paths
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    REPORT_TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates/report_templates')

    # RBAC Roles and Permissions
    ROLES_PERMISSIONS = {
        'Administrator': [
            'admin_access', 'manage_users', 'manage_settings',
            'view_gl', 'manage_gl', 'view_accounts', 'manage_accounts',
            'view_inventory', 'manage_inventory', 'view_payroll', 'manage_payroll',
            'view_tax', 'manage_tax', 'view_reports'
        ],
        'Chief Accountant': [
            'view_gl', 'manage_gl', 'view_accounts', 'manage_accounts',
            'view_inventory', 'view_payroll', 'manage_payroll',
            'view_tax', 'manage_tax', 'view_reports', 'approve_transactions'
        ],
        'Accountant': [
            'view_gl', 'manage_gl', 'view_accounts', 'manage_accounts',
            'view_inventory', 'view_payroll', 'view_tax', 'view_reports'
        ],
        'Auditor': [
            'view_gl', 'view_accounts', 'view_inventory', 'view_payroll',
            'view_tax', 'view_reports', 'view_audit_log'
        ],
        'Tax Specialist': [
            'view_tax', 'manage_tax', 'view_reports'
        ],
        'Inventory Manager': [
            'view_inventory', 'manage_inventory', 'view_reports'
        ],
        'Payroll Officer': [
            'view_payroll', 'manage_payroll', 'view_reports'
        ]
    }

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    DEBUG = False
    
    # Production security settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}