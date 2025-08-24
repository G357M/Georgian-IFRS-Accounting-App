# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Basic configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://username:password@localhost/georgian_accounting'
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
