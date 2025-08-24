from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from .models import Customer, Vendor, Invoice, InvoiceItem
from georgian_accounting.database import db
from georgian_accounting.utils.pdf_generator import generate_invoice_pdf
from decimal import Decimal
from datetime import datetime
import re
from georgian_accounting.utils.decorators import permission_required

accounts_bp = Blueprint(
    'accounts', 
    __name__, 
    template_folder='templates',
    url_prefix='/accounts'
)

@accounts_bp.route('/')
@login_required
@permission_required('view_accounts')
def index():
    return render_template('accounts_dashboard.html')

# Invoice Routes
@accounts_bp.route('/invoices')
@login_required
@permission_required('view_accounts')
def list_invoices():
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    return render_template('invoices.html', invoices=invoices)

@accounts_bp.route('/invoice/<int:invoice_id>')
@login_required
@permission_required('view_accounts')
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoice_detail.html', invoice=invoice)

@accounts_bp.route('/invoice/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_invoice():
    if request.method == 'POST':
        invoice_type = request.form.get('invoice_type')
        party_id = request.form.get('customer_id') if invoice_type == 'sales' else request.form.get('vendor_id')
        
        try:
            invoice = Invoice(
                invoice_number=request.form.get('invoice_number'),
                date=datetime.strptime(request.form.get('date'), '%Y-%m-%d'),
                customer_id=party_id if invoice_type == 'sales' else None,
                vendor_id=party_id if invoice_type == 'purchase' else None,
            )
            
            items_data = {}
            for key, value in request.form.items():
                match = re.match(r'items-(\d+)-(\w+)', key)
                if match:
                    index, field = match.groups()
                    if index not in items_data:
                        items_data[index] = {}
                    items_data[index][field] = value

            if not items_data:
                flash('Invoice must have at least one item.', 'danger')
                return redirect(request.url)

            for index, data in items_data.items():
                item = InvoiceItem(
                    description=data['description'],
                    quantity=Decimal(data['quantity']),
                    unit_price=Decimal(data['unit_price']),
                    vat_rate=Decimal(data['vat_rate'])
                )
                invoice.items.append(item)

            invoice.recalculate_totals()
            
            db.session.add(invoice)
            db.session.commit()
            flash('Invoice created successfully!', 'success')
            return redirect(url_for('accounts.list_invoices'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating invoice: {e}', 'danger')

    customers = Customer.query.all()
    vendors = Vendor.query.all()
    return render_template('invoice_form.html', customers=customers, vendors=vendors, action="New")

@accounts_bp.route('/invoice/edit/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == 'POST':
        try:
            invoice.invoice_number = request.form.get('invoice_number')
            invoice.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            
            # Clear old items
            for item in invoice.items:
                db.session.delete(item)

            # Add new items
            items_data = {}
            for key, value in request.form.items():
                match = re.match(r'items-(\d+)-(\w+)', key)
                if match:
                    index, field = match.groups()
                    if index not in items_data:
                        items_data[index] = {}
                    items_data[index][field] = value
            
            for index, data in items_data.items():
                item = InvoiceItem(
                    description=data['description'],
                    quantity=Decimal(data['quantity']),
                    unit_price=Decimal(data['unit_price']),
                    vat_rate=Decimal(data['vat_rate'])
                )
                invoice.items.append(item)

            invoice.recalculate_totals()
            db.session.commit()
            flash('Invoice updated successfully!', 'success')
            return redirect(url_for('accounts.list_invoices'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating invoice: {e}', 'danger')

    customers = Customer.query.all()
    vendors = Vendor.query.all()
    return render_template('invoice_form.html', invoice=invoice, customers=customers, vendors=vendors, action="Edit")


@accounts_bp.route('/invoice/pdf/<int:invoice_id>')
@login_required
@permission_required('view_accounts')
def download_invoice_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    pdf_buffer = generate_invoice_pdf(invoice)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f'invoice_{invoice.invoice_number}.pdf',
        mimetype='application/pdf'
    )


# Customer Routes
@accounts_bp.route('/customers')
@login_required
@permission_required('view_accounts')
def list_customers():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('customers.html', customers=customers)

@accounts_bp.route('/customer/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        tax_id = request.form.get('tax_id')
        is_foreign = 'is_foreign' in request.form

        if Customer.query.filter_by(name=name).first():
            flash('Customer with this name already exists.', 'danger')
        elif tax_id and Customer.query.filter_by(tax_id=tax_id).first():
            flash('Customer with this Tax ID already exists.', 'danger')
        else:
            new_customer = Customer(name=name, tax_id=tax_id, is_foreign=is_foreign)
            db.session.add(new_customer)
            db.session.commit()
            flash('Customer added successfully!', 'success')
            return redirect(url_for('accounts.list_customers'))
            
    return render_template('customer_form.html', action="Add")

# Vendor Routes
@accounts_bp.route('/vendors')
@login_required
@permission_required('view_accounts')
def list_vendors():
    vendors = Vendor.query.order_by(Vendor.name).all()
    return render_template('vendors.html', vendors=vendors)

@accounts_bp.route('/vendor/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_vendor():
    if request.method == 'POST':
        name = request.form.get('name')
        tax_id = request.form.get('tax_id')
        is_foreign = 'is_foreign' in request.form

        if Vendor.query.filter_by(name=name).first():
            flash('Vendor with this name already exists.', 'danger')
        elif tax_id and Vendor.query.filter_by(tax_id=tax_id).first():
            flash('Vendor with this Tax ID already exists.', 'danger')
        else:
            new_vendor = Vendor(name=name, tax_id=tax_id, is_foreign=is_foreign)
            db.session.add(new_vendor)
            db.session.commit()
            flash('Vendor added successfully!', 'success')
            return redirect(url_for('accounts.list_vendors'))
            
    return render_template('vendor_form.html', action="Add")