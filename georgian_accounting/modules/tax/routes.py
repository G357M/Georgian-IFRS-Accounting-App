from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from georgian_accounting.utils.decorators import permission_required
from .models import TaxRate
from georgian_accounting.database import db
from datetime import datetime
from decimal import Decimal

tax_bp = Blueprint(
    'tax', 
    __name__, 
    template_folder='templates',
    url_prefix='/tax'
)

@tax_bp.route('/')
@login_required
@permission_required('view_tax')
def index():
    return render_template('tax_dashboard.html')

@tax_bp.route('/tax-rates')
@login_required
@permission_required('view_tax')
def list_tax_rates():
    tax_rates = TaxRate.query.order_by(TaxRate.effective_date.desc()).all()
    return render_template('tax_rates.html', tax_rates=tax_rates)

@tax_bp.route('/tax-rate/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_tax')
def add_tax_rate():
    if request.method == 'POST':
        tax_type = request.form.get('tax_type')
        rate = Decimal(request.form.get('rate')) / 100 # Convert percentage to decimal
        effective_date = datetime.strptime(request.form.get('effective_date'), '%Y-%m-%d')
        end_date_str = request.form.get('end_date')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None

        # Basic validation: ensure no overlapping active rates for the same type
        existing_rate = TaxRate.query.filter_by(tax_type=tax_type, end_date=None).first()
        if existing_rate:
            flash(f'An active tax rate for {tax_type} already exists. Please set an end date for it first.', 'danger')
        else:
            new_tax_rate = TaxRate(
                tax_type=tax_type,
                rate=rate,
                effective_date=effective_date,
                end_date=end_date
            )
            db.session.add(new_tax_rate)
            db.session.commit()
            flash('Tax rate added successfully!', 'success')
            return redirect(url_for('tax.list_tax_rates'))
            
    return render_template('tax_rate_form.html', action="Add")

@tax_bp.route('/vat-declarations')
@login_required
@permission_required('view_tax')
def list_vat_declarations():
    # Will be implemented later
    return "<h1>List of VAT Declarations</h1>"

@tax_bp.route('/income-tax-declarations')
@login_required
@permission_required('view_tax')
def list_income_tax_declarations():
    # Will be implemented later
    return "<h1>List of Income Tax Declarations</h1>"

@tax_bp.route('/tax-calendar')
@login_required
@permission_required('view_tax')
def view_tax_calendar():
    # Will be implemented later
    return "<h1>Tax Calendar</h1>"
