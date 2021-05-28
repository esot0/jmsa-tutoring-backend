from mongoengine import *
from datetime import *


class TutoringSession(Document):
    date = DateTimeField()
    end_time = DateTimeField()
    tutor = DictField()
    student = DictField()
    subject = StringField()
    tutor_confirmed = BooleanField(default=False)
    student_confirmed = BooleanField(default=False)
    verified = BooleanField(default=False)


    def lengthInHours(self):
        difference = self.end_time - self.date
        res = round(difference.total_seconds()/(3600), 2)
        return res if res >=0 else 0
