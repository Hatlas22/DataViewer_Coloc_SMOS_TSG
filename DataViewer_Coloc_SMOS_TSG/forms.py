from flask_wtf import FlaskForm
from wtforms import (StringField, IntegerField, BooleanField,
                     RadioField, SelectField, DateField)
from wtforms.validators import InputRequired, Length


class CourseForm(FlaskForm):
    meanr_ave = StringField('Type de moyenne', validators=[InputRequired(),
                                                           Length(min=1, max=100)])
    tsg_product = SelectField('Produit TSG', choices=[(1, 'one'), (2, 'two')])
    dataset = SelectField('Produit SMOS', choices=[(1, 'one'), (2, 'two')])
    orbit_type = RadioField("Type d'orbite",
                            choices=['Beginner', 'Intermediate', 'Advanced'],
                            validators=[InputRequired()])
    transects = SelectField('Transects', choices=[(1, 'one'), (2, 'two')])
    limdate_in = DateField("Date min", format='%d/%m/%Y')
    limdate_out = DateField("Date max", format='%d/%m/%Y')
    user = StringField('utilisateur', validators=[InputRequired(),
                                                  Length(min=1, max=100)])
    min_length = IntegerField('Longueur minimale', validators=[InputRequired()])
    progress_recorder = BooleanField('enregistreur de progression')
