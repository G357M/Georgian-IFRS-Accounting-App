from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SubmitField, DecimalField, DateField, FieldList, FormField, RadioField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField
from .models import AccountType, Account, Customer, Vendor
from datetime import datetime

# A factory to create a query for QuerySelectField
def get_account_types():
    return AccountType.query.order_by(AccountType.name)

def get_parent_accounts():
    return Account.query.order_by(Account.account_number)

def get_customers():
    return Customer.query.order_by(Customer.name)

def get_vendors():
    return Vendor.query.order_by(Vendor.name)

class AccountTypeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=50)])
    description = TextAreaField('Description')
    submit = SubmitField('Submit')

    def validate_name(self, name):
        # Check for uniqueness on edit
        if self.obj and self.obj.name == name.data:
            return
        if AccountType.query.filter_by(name=name.data).first():
            raise ValidationError('An account type with this name already exists.')

class AccountForm(FlaskForm):
    account_number = StringField('Account Number', validators=[DataRequired(), Length(max=50)])
    account_name = StringField('Account Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    account_type_id = QuerySelectField('Account Type', query_factory=get_account_types, get_label='name', allow_blank=False, validators=[DataRequired()])
    parent_id = QuerySelectField('Parent Account', query_factory=get_parent_accounts, get_label='account_name', allow_blank=True, blank_text='-- No Parent --')
    is_active = BooleanField('Is Active', default=True)
    submit = SubmitField('Submit')

    def validate_account_number(self, account_number):
        if self.obj and self.obj.account_number == account_number.data:
            return
        if Account.query.filter_by(account_number=account_number.data).first():
            raise ValidationError('An account with this number already exists.')

    def validate_account_name(self, account_name):
        if self.obj and self.obj.account_name == account_name.data:
            return
        if Account.query.filter_by(account_name=account_name.data).first():
            raise ValidationError('An account with this name already exists.')

class CustomerForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    tax_id = StringField('Tax ID', validators=[Optional(), Length(max=20)])
    is_foreign = BooleanField('Is Foreign')
    submit = SubmitField('Submit')

    def validate_name(self, name):
        if self.obj and self.obj.name == name.data:
            return
        if Customer.query.filter_by(name=name.data).first():
            raise ValidationError('A customer with this name already exists.')

    def validate_tax_id(self, tax_id):
        if tax_id.data:
            if self.obj and self.obj.tax_id == tax_id.data:
                return
            if Customer.query.filter_by(tax_id=tax_id.data).first():
                raise ValidationError('A customer with this Tax ID already exists.')

class VendorForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    tax_id = StringField('Tax ID', validators=[Optional(), Length(max=20)])
    is_foreign = BooleanField('Is Foreign')
    submit = SubmitField('Submit')

    def validate_name(self, name):
        if self.obj and self.obj.name == name.data:
            return
        if Vendor.query.filter_by(name=name.data).first():
            raise ValidationError('A vendor with this name already exists.')

    def validate_tax_id(self, tax_id):
        if tax_id.data:
            if self.obj and self.obj.tax_id == tax_id.data:
                return
            if Vendor.query.filter_by(tax_id=tax_id.data).first():
                raise ValidationError('A vendor with this Tax ID already exists.')

class InvoiceItemForm(FlaskForm):
    # Note: This is a FlaskForm for validation, but we use it with FormField
    class Meta:
        csrf = False # No CSRF for subforms
        
    description = StringField('Description', validators=[DataRequired()])
    quantity = DecimalField('Quantity', default=1, validators=[DataRequired()])
    unit_price = DecimalField('Unit Price', default=0.00, validators=[DataRequired()])
    vat_rate = DecimalField('VAT Rate', default=0.18, validators=[DataRequired()])

class InvoiceForm(FlaskForm):
    invoice_type = RadioField('Type', choices=[('sales', 'Sales'), ('purchase', 'Purchase')], default='sales', validators=[DataRequired()])
    customer_id = QuerySelectField('Customer', query_factory=get_customers, get_label='name', allow_blank=True)
    vendor_id = QuerySelectField('Vendor', query_factory=get_vendors, get_label='name', allow_blank=True)
    invoice_number = StringField('Invoice Number', validators=[DataRequired()])
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()], default=datetime.today)
    items = FieldList(FormField(InvoiceItemForm), min_entries=1)
    submit = SubmitField('Save Invoice')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        if self.invoice_type.data == 'sales' and not self.customer_id.data:
            self.customer_id.errors.append('Customer is required for a sales invoice.')
            return False
        if self.invoice_type.data == 'purchase' and not self.vendor_id.data:
            self.vendor_id.errors.append('Vendor is required for a purchase invoice.')
            return False
        return True

class DeleteForm(FlaskForm):
    """A simple form for CSRF protection on delete actions."""
    submit = SubmitField('Delete')