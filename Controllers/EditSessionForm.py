from wtforms import StringField,  Form

class EditSessionForm(Form):
    subject = StringField('Subject')

    date = StringField('Date')

    other_user = StringField('Other User')
