from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from georgian_accounting.modules.accounts.models import Account
from .models import Transaction, JournalEntry
from georgian_accounting.database import db
from decimal import Decimal
from datetime import datetime
from georgian_accounting.utils.decorators import permission_required
from georgian_accounting.modules.general_ledger.reports import generate_balance_sheet, generate_income_statement
from georgian_accounting.core.models import Company
from .forms import AccountForm, TransactionForm # Import new forms

general_ledger_bp = Blueprint(
    'general_ledger', 
    __name__, 
    template_folder='templates'
)

@general_ledger_bp.route('/chart-of-accounts')
@login_required
@permission_required('view_gl')
def chart_of_accounts():
    accounts = Account.query.order_by(Account.account_number).all()
    return render_template('chart_of_accounts.html', accounts=accounts)

@general_ledger_bp.route('/account/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_gl')
def add_account():
    form = AccountForm()
    if form.validate_on_submit():
        new_account = Account()
        form.populate_obj(new_account)
        db.session.add(new_account)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('general_ledger.chart_of_accounts'))
    return render_template('account_form.html', form=form, action="Add")

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
    form = TransactionForm()
    if form.validate_on_submit():
        try:
            # --- Start of logic that should be in a service ---
            new_trans = Transaction(
                date=form.date.data, 
                description=form.description.data
            )
            
            debit_entry = JournalEntry(
                transaction=new_trans,
                account=form.debit_account.data,
                debit=form.amount.data
            )
            credit_entry = JournalEntry(
                transaction=new_trans,
                account=form.credit_account.data,
                credit=form.amount.data
            )
            
            debit_account = form.debit_account.data
            credit_account = form.credit_account.data
            amount = form.amount.data
            
            # This logic is incorrect for a real accounting system and needs review.
            # Balance updates should be handled carefully based on account type.
            if debit_account.account_type_rel.name in ['Asset', 'Expense']:
                debit_account.balance = debit_account.balance + amount
            else:
                debit_account.balance = debit_account.balance - amount

            if credit_account.account_type_rel.name in ['Liability', 'Equity', 'Revenue']:
                credit_account.balance = credit_account.balance + amount
            else:
                credit_account.balance = credit_account.balance - amount
            # --- End of logic that should be in a service ---

            db.session.add(new_trans)
            db.session.add(debit_entry)
            db.session.add(credit_entry)
            db.session.commit()

            flash('Transaction created successfully!', 'success')
            return redirect(url_for('general_ledger.chart_of_accounts'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating transaction: {e}', 'danger')

    return render_template('transaction_form.html', form=form)

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
