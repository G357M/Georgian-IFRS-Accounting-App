from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from .models import Product

class ProductForm(FlaskForm):
    code = StringField('Product Code', validators=[DataRequired()])
    name = StringField('Product Name', validators=[DataRequired()])
    category = StringField('Category')
    unit_of_measure = StringField('Unit of Measure')
    is_vat_exempt = BooleanField('VAT Exempt')
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Submit')

    def __init__(self, original_code=None, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.original_code = original_code

    def validate_code(self, code):
        if code.data != self.original_code:
            if Product.query.filter_by(code=code.data).first():
                raise ValidationError('A product with this code already exists.')

class DeleteForm(FlaskForm):
    """A simple form for CSRF protection on delete actions."""
    submit = SubmitField('Delete')