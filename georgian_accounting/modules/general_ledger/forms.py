from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, DateField, DecimalField
from wtforms.validators import DataRequired, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField
from georgian_accounting.modules.accounts.models import Account
from datetime import date

def get_active_accounts():
    return Account.query.filter_by(is_active=True).order_by(Account.account_number)

class AccountForm(FlaskForm):
    code = StringField('Account Code', validators=[DataRequired()])
    name = StringField('Account Name', validators=[DataRequired()])
    account_type = SelectField(
        'Account Type',
        choices=[
            ('Asset', 'Asset'), 
            ('Liability', 'Liability'), 
            ('Equity', 'Equity'), 
            ('Revenue', 'Revenue'), 
            ('Expense', 'Expense')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Submit')

    def validate_code(self, code):
        if Account.query.filter_by(account_number=code.data).first():
            raise ValidationError('An account with this code already exists.')

class TransactionForm(FlaskForm):
    date = DateField('Date', default=date.today, validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    amount = DecimalField('Amount', places=2, validators=[DataRequired()])
    debit_account = QuerySelectField('Debit Account', query_factory=get_active_accounts, get_label='account_name', allow_blank=False)
    credit_account = QuerySelectField('Credit Account', query_factory=get_active_accounts, get_label='account_name', allow_blank=False)
    submit = SubmitField('Create Transaction')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        if self.debit_account.data == self.credit_account.data:
            self.debit_account.errors.append('Debit and Credit accounts cannot be the same.')
            return False
        return True