from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, DateField, DecimalField
from wtforms.validators import DataRequired, ValidationError
from .models import Employee
from datetime import date

class EmployeeForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    personal_id = StringField('Personal ID', validators=[DataRequired()])
    hire_date = DateField('Hire Date', default=date.today, validators=[DataRequired()])
    salary = DecimalField('Salary', places=2, validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    in_pension_scheme = BooleanField('In Pension Scheme', default=True)
    submit = SubmitField('Submit')

    def __init__(self, original_personal_id=None, *args, **kwargs):
        super(EmployeeForm, self).__init__(*args, **kwargs)
        self.original_personal_id = original_personal_id

    def validate_personal_id(self, personal_id):
        if personal_id.data != self.original_personal_id:
            if Employee.query.filter_by(personal_id=personal_id.data).first():
                raise ValidationError('An employee with this Personal ID already exists.')

class DeleteForm(FlaskForm):
    """A simple form for CSRF protection on delete actions."""
    submit = SubmitField('Delete')