from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from .models import Customer, Vendor, Invoice, InvoiceItem, Account, AccountType
from georgian_accounting.database import db
from georgian_accounting.utils.pdf_generator import generate_invoice_pdf
from georgian_accounting.utils.decorators import permission_required
# Import forms
from .forms import (
    AccountTypeForm, AccountForm, CustomerForm, VendorForm, 
    InvoiceForm, DeleteForm
)

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

# Account Type Routes
@accounts_bp.route('/account_types')
@login_required
@permission_required('view_accounts')
def list_account_types():
    account_types = AccountType.query.order_by(AccountType.name).all()
    delete_form = DeleteForm() # For delete buttons
    return render_template('account_types.html', account_types=account_types, delete_form=delete_form)

@accounts_bp.route('/account_type/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_account_type():
    form = AccountTypeForm()
    if form.validate_on_submit():
        new_account_type = AccountType()
        form.populate_obj(new_account_type)
        db.session.add(new_account_type)
        db.session.commit()
        flash('Account type added successfully!', 'success')
        return redirect(url_for('accounts.list_account_types'))
    return render_template('account_type_form.html', form=form, action="Add")

@accounts_bp.route('/account_type/edit/<int:type_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def edit_account_type(type_id):
    account_type = AccountType.query.get_or_404(type_id)
    form = AccountTypeForm(obj=account_type)
    if form.validate_on_submit():
        form.populate_obj(account_type)
        db.session.commit()
        flash('Account type updated successfully!', 'success')
        return redirect(url_for('accounts.list_account_types'))
    return render_template('account_type_form.html', form=form, action="Edit")

@accounts_bp.route('/account_type/delete/<int:type_id>', methods=['POST'])
@login_required
@permission_required('manage_accounts')
def delete_account_type(type_id):
    form = DeleteForm()
    if form.validate_on_submit():
        account_type = AccountType.query.get_or_404(type_id)
        try:
            db.session.delete(account_type)
            db.session.commit()
            flash('Account type deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting account type: {e}', 'danger')
    else:
        flash('Invalid request.', 'danger')
    return redirect(url_for('accounts.list_account_types'))

# Chart of Accounts Routes
@accounts_bp.route('/chart_of_accounts')
@login_required
@permission_required('view_accounts')
def list_chart_of_accounts():
    accounts = Account.query.order_by(Account.account_number).all()
    delete_form = DeleteForm()
    return render_template('chart_of_accounts.html', accounts=accounts, delete_form=delete_form)

@accounts_bp.route('/account/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_account():
    form = AccountForm()
    # Manually set choices for parent_id to exclude self
    form.parent_id.query = Account.query.order_by(Account.account_number)
    if form.validate_on_submit():
        new_account = Account()
        # populate_obj doesn't work well with QuerySelectField's object, so we do it manually
        new_account.account_number = form.account_number.data
        new_account.account_name = form.account_name.data
        new_account.description = form.description.data
        new_account.account_type_id = form.account_type_id.data.id
        new_account.parent_id = form.parent_id.data.id if form.parent_id.data else None
        new_account.is_active = form.is_active.data
        
        db.session.add(new_account)
        db.session.commit()
        flash('Account added successfully!', 'success')
        return redirect(url_for('accounts.list_chart_of_accounts'))
    return render_template('account_form.html', form=form, action="Add")

@accounts_bp.route('/account/edit/<int:account_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def edit_account(account_id):
    account = Account.query.get_or_404(account_id)
    form = AccountForm(obj=account)
    form.account_type_id.data = account.account_type_rel # Pre-select QuerySelectField
    form.parent_id.data = account.parent # Pre-select QuerySelectField
    # Exclude self from parent choices
    form.parent_id.query = Account.query.filter(Account.id != account_id).order_by(Account.account_number)

    if form.validate_on_submit():
        account.account_number = form.account_number.data
        account.account_name = form.account_name.data
        account.description = form.description.data
        account.account_type_id = form.account_type_id.data.id
        account.parent_id = form.parent_id.data.id if form.parent_id.data else None
        account.is_active = form.is_active.data
        db.session.commit()
        flash('Account updated successfully!', 'success')
        return redirect(url_for('accounts.list_chart_of_accounts'))
    return render_template('account_form.html', form=form, action="Edit")

@accounts_bp.route('/account/delete/<int:account_id>', methods=['POST'])
@login_required
@permission_required('manage_accounts')
def delete_account(account_id):
    form = DeleteForm()
    if form.validate_on_submit():
        account = Account.query.get_or_404(account_id)
        try:
            db.session.delete(account)
            db.session.commit()
            flash('Account deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting account: {e}', 'danger')
    else:
        flash('Invalid request.', 'danger')
    return redirect(url_for('accounts.list_chart_of_accounts'))




# Customer Routes
@accounts_bp.route('/customers')
@login_required
@permission_required('view_accounts')
def list_customers():
    customers = Customer.query.order_by(Customer.name).all()
    delete_form = DeleteForm()  # For CSRF protection on delete buttons
    return render_template('customers.html', customers=customers, delete_form=delete_form)

@accounts_bp.route('/customer/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        new_customer = Customer()
        form.populate_obj(new_customer)
        db.session.add(new_customer)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('accounts.list_customers'))
    return render_template('customer_form.html', form=form, action="Add")

@accounts_bp.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer)
    if form.validate_on_submit():
        form.populate_obj(customer)
        db.session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('accounts.list_customers'))
    return render_template('customer_form.html', form=form, action="Edit")

@accounts_bp.route('/customer/delete/<int:customer_id>', methods=['POST'])
@login_required
@permission_required('manage_accounts')
def delete_customer(customer_id):
    form = DeleteForm()
    if form.validate_on_submit(): # This validates the CSRF token
        customer = Customer.query.get_or_404(customer_id)
        try:
            db.session.delete(customer)
            db.session.commit()
            flash('Customer deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting customer: {e}', 'danger')
    else:
        flash('Invalid request. Could not delete customer.', 'danger')
    return redirect(url_for('accounts.list_customers'))


# Invoice Routes
@accounts_bp.route('/invoices')
@login_required
@permission_required('view_accounts')
def list_invoices():
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    delete_form = DeleteForm() # Create form for CSRF protection
    return render_template('invoices.html', invoices=invoices, delete_form=delete_form)

@accounts_bp.route('/invoice/view/<int:invoice_id>')
@login_required
@permission_required('view_accounts')
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoice_detail.html', invoice=invoice)

@accounts_bp.route('/invoice/delete/<int:invoice_id>', methods=['POST'])
@login_required
@permission_required('manage_accounts')
def delete_invoice(invoice_id):
    form = DeleteForm()
    if form.validate_on_submit(): # Validates CSRF token
        invoice = Invoice.query.get_or_404(invoice_id)
        try:
            db.session.delete(invoice)
            db.session.commit()
            flash('Invoice deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting invoice: {e}', 'danger')
    else:
        flash('Invalid request. Could not delete invoice.', 'danger')
    return redirect(url_for('accounts.list_invoices'))

@accounts_bp.route('/invoice/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def add_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        try:
            invoice = Invoice()
            # Manually populate due to complexity
            invoice.invoice_number = form.invoice_number.data
            invoice.date = form.date.data
            invoice.customer_id = form.customer_id.data.id if form.invoice_type.data == 'sales' else None
            invoice.vendor_id = form.vendor_id.data.id if form.invoice_type.data == 'purchase' else None
            
            # Clear any default items and add from form
            invoice.items = []
            for item_form in form.items:
                item = InvoiceItem()
                item_form.populate_obj(item)
                invoice.items.append(item)

            db.session.add(invoice)
            db.session.commit()
            flash('Invoice created successfully!', 'success')
            return redirect(url_for('accounts.list_invoices'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating invoice: {e}', 'danger')
    
    return render_template('invoice_form.html', form=form, action="New")


@accounts_bp.route('/invoice/edit/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_accounts')
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == 'POST':
        try:
            invoice.invoice_number = request.form.get('invoice_number')
            invoice.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            
            # A more efficient way is to update/add/delete items, 
            # but clearing and re-adding is simpler to implement.
            invoice.items = [] # Clear old items using the relationship
            db.session.flush() # Persist the deletion of old items

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
                    description=data.get('description'),
                    quantity=Decimal(data.get('quantity', '0')),

                    unit_price=Decimal(data.get('unit_price', '0')),

                    vat_rate=Decimal(data.get('vat_rate', '0.18'))
                )
                invoice.items.append(item)

            # invoice.recalculate_totals() # REMOVE THIS LINE
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