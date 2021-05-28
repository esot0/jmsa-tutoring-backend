from wtforms import StringField, DateTimeField, validators, Form


class CreateSessionForm(Form):
    subject = StringField('Subject',
                          [validators.DataRequired()])
    date = StringField('Date',
                       [validators.DataRequired()])

    other_user = StringField('Other User',
                       [validators.DataRequired()])

    # implement assurance the date string pattern matches the one I'm parsing
