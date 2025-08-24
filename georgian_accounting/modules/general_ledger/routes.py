from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .models import Account, Transaction, JournalEntry
from georgian_accounting.database import db
from decimal import Decimal
from datetime import datetime
from georgian_accounting.utils.decorators import permission_required
from georgian_accounting.modules.general_ledger.reports import generate_balance_sheet, generate_income_statement
from georgian_accounting.core.models import Company

general_ledger_bp = Blueprint(
    'general_ledger', 
    __name__, 
    template_folder='templates'
)

@general_ledger_bp.route('/chart-of-accounts')
@login_required
@permission_required('view_gl')
def chart_of_accounts():
    accounts = Account.query.order_by(Account.code).all()
    return render_template('chart_of_accounts.html', accounts=accounts)

@general_ledger_bp.route('/account/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_gl')
def add_account():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        account_type = request.form.get('account_type')
        
        if Account.query.filter_by(code=code).first():
            flash('Account code already exists.', 'danger')
        else:
            new_account = Account(code=code, name=name, account_type=account_type)
            db.session.add(new_account)
            db.session.commit()
            flash('Account created successfully!', 'success')
            return redirect(url_for('general_ledger.chart_of_accounts'))
            
    return render_template('account_form.html', action="Add")

@general_ledger_bp.route('/account/<int:account_id>')
@login_required
@permission_required('view_gl')
def account_detail(account_id):
    account = Account.query.get_or_404(account_id)
    return render_template('account_detail.html', account=account)

@general_ledger_bp.route('/transaction/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_gl')
def add_transaction():
    if request.method == 'POST':
        date_str = request.form.get('date')
        description = request.form.get('description')
        debit_account_id = int(request.form.get('debit_account'))
        debit_amount = Decimal(request.form.get('debit_amount'))
        credit_account_id = int(request.form.get('credit_account'))
        credit_amount = Decimal(request.form.get('credit_amount'))

        if debit_amount != credit_amount or debit_account_id == credit_account_id:
            flash('Debits must equal credits and accounts must be different.', 'danger')
        else:
            try:
                date = datetime.fromisoformat(date_str)
                
                new_trans = Transaction(date=date, description=description)
                
                debit_entry = JournalEntry(
                    transaction=new_trans,
                    account_id=debit_account_id,
                    debit=debit_amount
                )
                credit_entry = JournalEntry(
                    transaction=new_trans,
                    account_id=credit_account_id,
                    credit=credit_amount
                )
                
                debit_account = Account.query.get(debit_account_id)
                credit_account = Account.query.get(credit_account_id)
                
                # This is a simplification. Real accounting rules are more complex.
                if debit_account.account_type in ['Asset', 'Expense']:
                    debit_account.balance += debit_amount
                else:
                    debit_account.balance -= debit_amount

                if credit_account.account_type in ['Liability', 'Equity', 'Revenue']:
                    credit_account.balance += credit_amount
                else:
                    credit_account.balance -= credit_amount

                db.session.add(new_trans)
                db.session.add(debit_entry)
                db.session.add(credit_entry)
                db.session.commit()

                flash('Transaction created successfully!', 'success')
                return redirect(url_for('general_ledger.chart_of_accounts'))

            except Exception as e:
                db.session.rollback()
                flash(f'Error creating transaction: {e}', 'danger')

    accounts = Account.query.order_by(Account.code).all()
    return render_template('transaction_form.html', accounts=accounts)

# Financial Statements Routes
@general_ledger_bp.route('/financial-statements')
@login_required
@permission_required('view_gl')
def financial_statements_dashboard():
    return render_template('financial_statements_dashboard.html')

@general_ledger_bp.route('/balance-sheet')
@login_required
@permission_required('view_gl')
def balance_sheet_report():
    # For now, use a dummy company and period
    company = Company.query.first() # Get the first company, or create a dummy one
    if not company:
        company = Company(name="Dummy Company", registration_number="12345", tax_id="67890")
        db.session.add(company)
        db.session.commit()

    report_data = generate_balance_sheet(company, datetime(2024, 1, 1), datetime(2024, 12, 31))
    return render_template('balance_sheet_report.html', report=report_data)

@general_ledger_bp.route('/income-statement')
@login_required
@permission_required('view_gl')
def income_statement_report():
    # For now, use a dummy company and period
    company = Company.query.first() # Get the first company, or create a dummy one
    if not company:
        company = Company(name="Dummy Company", registration_number="12345", tax_id="67890")
        db.session.add(company)
        db.session.commit()

    report_data = generate_income_statement(company, datetime(2024, 1, 1), datetime(2024, 12, 31))
    return render_template('income_statement_report.html', report=report_data)
