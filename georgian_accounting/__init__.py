from flask import Flask, render_template
from flask_login import LoginManager
from .config import config
from .database import db

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .modules.auth.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Import and register blueprints
    from .modules.general_ledger.routes import general_ledger_bp
    app.register_blueprint(general_ledger_bp)

    from .modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from .modules.accounts.routes import accounts_bp
    app.register_blueprint(accounts_bp)

    from .modules.inventory.routes import inventory_bp
    app.register_blueprint(inventory_bp)

    from .modules.payroll.routes import payroll_bp
    app.register_blueprint(payroll_bp)

    from .modules.reporting.routes import reporting_bp
    app.register_blueprint(reporting_bp)

    # Import audit listeners to register them
    from .modules.audit import listeners

    with app.app_context():
        # Import all models here to ensure they are registered before creating tables
        from .modules.general_ledger import models
        from .modules.auth import models
        from .modules.audit import models
        from .modules.accounts import models
        from .modules.inventory import models
        from .modules.payroll import models
        from flask import Flask, render_template
from flask_login import LoginManager
from .config import config
from .database import db

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .modules.auth.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Import and register blueprints
    from .modules.general_ledger.routes import general_ledger_bp
    app.register_blueprint(general_ledger_bp)

    from .modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from .modules.accounts.routes import accounts_bp
    app.register_blueprint(accounts_bp)

    from .modules.inventory.routes import inventory_bp
    app.register_blueprint(inventory_bp)

    from .modules.payroll.routes import payroll_bp
    app.register_blueprint(payroll_bp)

    from .modules.reporting.routes import reporting_bp
    app.register_blueprint(reporting_bp)

    from .modules.tax.routes import tax_bp
    app.register_blueprint(tax_bp)

    # Import audit listeners to register them
    from .modules.audit import listeners

    with app.app_context():
        # Import all models here to ensure they are registered before creating tables
        from .core import models as core_models
        from .modules.general_ledger import models as gl_models
        from .modules.auth import models as auth_models
        from .modules.audit import models as audit_models
        from .modules.accounts import models as accounts_models
        from .modules.inventory import models as inventory_models
        from .modules.payroll import models as payroll_models
        from .modules.tax import models as tax_models
        db.create_all()

    @app.route('/')
    def index():
        return render_template('dashboard.html')

    return app


    @app.route('/')
    def index():
        return render_template('dashboard.html')

    return app
