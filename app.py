from gevent import monkey
monkey.patch_all()
from mongoengine.errors import NotUniqueError
import os
import flask
import flask_cors
import flask_praetorian

from dotenv import load_dotenv
from flask import request, jsonify, session
from flask_cors import CORS, cross_origin
from mongoengine import connect
import traceback
from mongoengine.queryset.visitor import Q
from Schemas.TutoringSession import TutoringSession
from Schemas.Message import Message
from Schemas.Subject import Subject
from Schemas.User import User
from datetime import *
from bson.objectid import ObjectId
from flask_mail import Mail;
from werkzeug.utils import secure_filename
from flask import send_from_directory
from flask_socketio import SocketIO

load_dotenv()

UPLOAD_FOLDER = 'profile_pictures'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = flask.Flask(__name__)


CONNECTION = connect("testing", host=os.getenv("CONNECTION_STRING"))

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config["MAIL_USERNAME"] = "sotoemily03@gmail.com"
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_CONNECTION")
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

app.config["PRAETORIAN_EMAIL_TEMPLATE"] = './email.html'
app.config["PRATEORIAN_CONFIRMATION_SENDER"] = "sotoemily03@gmail.com"
app.config["PRAETORIAN_CONFIRMATION_URI"] = "http://localhost:3000/user/finalize_registration"
app.config["PRAETORIAN_CONFIRMATION_SUBJECT"] = "[JMSA Tutoring] Please Verify Your Account"

app.config["JWT_ACCESS_LIFESPAN"] = {"hours": 24}
app.config["JWT_REFRESH_LIFESPAN"] = {"days": 30}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

guard = flask_praetorian.Praetorian()

guard.init_app(app, user_class=User)
CORS(app, origins=["http://localhost:3000","https://jmsa-tutoring.netlify.app"])
socketio = SocketIO(app, logger=True, engineio_logger=True, cors_allowed_origins=["http://localhost:3000","https://jmsa-tutoring.netlify.app"])

mail = Mail(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_dates(input_date_list):
    formatted_list = []
    for date_input in input_date_list:
        datetime_formatted = datetime.strptime(date_input, "%m/%d/%Y")
        formatted_list.append(datetime_formatted)
    return formatted_list


@app.route("/", defaults={"path": ""})
@app.route("/<string:path>")
@app.route("/<path:path>")
def index():
	return ({"Welcome to JMSA Tutoring", 200})

@app.route('/user/<username>/sessions', methods=['GET'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def user_sessions(username):
    user = User.objects.get(username=username)
    if "tutor" in user.rolenames:
        tutor_sessions = TutoringSession.objects(tutor__id=user.id).all()
    if "student" in user.rolenames:
        tutor_sessions = TutoringSession.objects(student__id=user.id).all()
    return tutor_sessions.to_json()

@app.route('/sessions', methods=['GET'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def all_sessions():
    tutor_sessions = TutoringSession.objects().all()
    return tutor_sessions.to_json()
#rtc data

@app.route('/user/sessions/new', methods=['GET', 'POST'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def create_session():
    try:
        tutoring_session = TutoringSession()
        datetime_formatted = datetime.strptime(request.json['date'], "%m/%d/%Y %I:%M %p %z")
        end_datetime_formatted = datetime.strptime(request.json['end_date'], "%m/%d/%Y %I:%M %p %z")
        tutoring_session.date = datetime_formatted
        tutoring_session.end_time = end_datetime_formatted
        tutoring_session.subject = request.json['subject']

        if "tutor" in flask_praetorian.current_user().roles:
            tutor = flask_praetorian.current_user()
            student = User.objects.get(username=request.json['other_user']['username'])
        else:
            student = flask_praetorian.current_user()
            tutor = User.objects.get(username=request.json['other_user']['username'])

        tutoring_session.tutor = {
            "id": tutor.id,
            "username": tutor.username
        }
        
        tutoring_session.student = {
            "id": student.id,
            "username": student.username
        }
        
        tutoring_session.save()

        tutor.sessions.append(tutoring_session)
        student.sessions.append(tutoring_session)

        tutor.save()
        student.save()
    
        return tutoring_session.to_json()
    except Exception as e:
        print(str(e))
        return str(e)


@app.route('/user/sessions/<id>/edit', methods=['GET', 'POST'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def session_edit(id):
    session_to_edit = TutoringSession.objects.get(id=id)

    if request.method == "POST":
            print(request.json)
            session_to_edit.date=datetime.strptime(request.json['date'], "%m/%d/%Y %I:%M %p %z") if 'date' in request.json else session_to_edit.date
            session_to_edit.subject = request.json['subject'] if 'subject' in request.json else session_to_edit.subject
            session_to_edit.end_time = datetime.strptime(request.json['end_time'], "%m/%d/%Y %I:%M %p %z") if 'end_time' in request.json else session_to_edit.end_time
            session_to_edit.tutor_confirmed = request.json['tutor_confirmed'] if 'tutor_confirmed' in request.json else session_to_edit.tutor_confirmed
            session_to_edit.student_confirmed = request.json['student_confirmed'] if 'student_confirmed' in request.json else session_to_edit.student_confirmed
            session_to_edit.save()

            print(session_to_edit.date)
            print(session_to_edit.end_time)
            return session_to_edit.to_json();
    if request.method == "DELETE":
        session_to_edit.delete()
            
    if request.method == "GET":
        return session_to_edit.to_json()


@app.route('/user/<username>/chat/<recipient>', methods=['GET', 'POST'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def chat(username, recipient):
    try: 
       user = flask_praetorian.current_user()   
       if request.method=="POST":
           message = Message()
           message.sender = user.id
           message.recipient = ObjectId(request.json['recipient'])
           message.body = request.json['body']
           message.timestamp = datetime.now()
           message.save()

           recipient = User.objects.get(id=request.json['recipient'])
           recipient.messages.append(message)
           user.messages.append(message)
           user.save()
           recipient.save() 
           return message.to_json()
       elif request.method=="GET":
           return Message.objects.filter(Q(recipient=recipient) & Q(sender=user.id) | Q(sender=recipient) & Q(recipient=user.id)).to_json()
    except Exception as e:
        traceback.print_exc()
        return 'Invalid operation'

@app.route('/user/sign_in', methods=['POST'])
@cross_origin(supports_credentials=True)
def login_page():
    try:
        if request.method == "POST":
            user = guard.authenticate(username=request.json['username'], password=request.json['password'])
            if(user and user.is_active):
                user.id = str(user.id)
                ret = {"access_token": guard.encode_jwt_token(user, override_access_lifespan=None, override_refresh_lifespan=None, bypass_user_check=False, is_registration_token=False, is_reset_token=False, username=user.username)}
                session['jwt_token'] = ret
                return jsonify(ret)
            else:
               return 'Invalid credentials', 401
    except Exception as e:
        print(e)
        print(traceback.print_exc)
        return 'Invalid credentials', 401

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/user/sign_up', methods=['GET', 'POST'])
def api_sign_up():
    try:
        if request.method == 'POST':
            print(request.form)
            user = User()
            user.id=ObjectId()
            if 'username' in request.form:
                user.username = request.form.get('username')
            if 'full_name' in request.form:
                user.full_name = request.form.get('full_name')
            if 'password' in request.form:
                user.hashed_password = guard.hash_password(request.form.get('password'))
            if 'roles' in request.form:
                user.roles = request.form.get('roles')
            if 'us_phone_number' in request.form:
                user.us_phone_number = request.form.get('us_phone_number')
            if 'availability' in request.form and len(request.form['availability'])>0:
                user.availability = parse_dates(str(request.form.getlist('availability')).replace("['", "").replace("']", "").split(','))
            if 'email' in request.form:
                user.email = request.form.get('email')
            if 'tutor_subjects' in request.form: 
                user.tutor_subjects = request.form.getlist('tutor_subjects')
            if 'biography' in request.form:
                user.biography = request.form.get('biography')
            if 'profile_picture' in request.files:
                profile_picture = request.files['profile_picture']
                if allowed_file(profile_picture.filename):
                    filename = secure_filename(profile_picture.filename)
                    profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))
                    user.profile_picture = os.path.join(app.config['UPLOAD_FOLDER'],filename)

            guard.send_registration_email(user.email, user=user, confirmation_sender="sotoemily03@gmail.com", confirmation_uri="http://localhost:3000/finalize_registration" )
            user.save()
            return "Success"
    except NotUniqueError as n:
        return "Duplicate key", 200
    except Exception as e:
        print(e)
        return "Failure", 422
@app.route('/finalize', methods=['GET'])
def finalize():
    try:
        registration_token = guard.read_token_from_header()
        user = guard.get_user_from_registration_token(registration_token)
        user.is_active = True
        user.save()
        ret = {'access_token': guard.encode_jwt_token(user, override_access_lifespan=None, override_refresh_lifespan=None, bypass_user_check=False, is_registration_token=False, is_reset_token=False, username=user.username)}
        return (flask.jsonify(ret), 200)
    except Exception as e:
        print("EXCEPTION: " , e)
        return str(e)

@app.route('/send_password_email', methods=['POST'])
def send_email():
    try:
        return guard.send_reset_email(email=request.json['email'], reset_sender="sotoemily03@gmail.com", reset_uri="http://localhost:3000/reset_password")
    except Exception as e:
        print(e)
        return str(e)
        
@app.route('/reset_password', methods=['POST'])
def reset_password():
    try:
        reset_token = guard.read_token_from_header()
        user = guard.validate_reset_token(reset_token)
        if(user):  
            print("Reset successful")
            user.hashed_password=guard.hash_password(request.json['password'])
            guard.verify_and_update(user=user, password=request.json['password'])
            user.save()
            return ('200')
    except Exception as e:
        print(e)
        return str(e)
        
@app.route('/user/<username>', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_user(username):
    user = User.objects.get(username=username)
    return user.to_json()

@app.route('/profile_pictures/<filename>', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_profile_picture(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],filename,  as_attachment=True)

@app.route('/user/<username>/edit', methods=['GET', 'POST', 'DELETE'])
@cross_origin(supports_credentials=True)
def user_edit(username):
    user_to_edit = User.objects.get(username=username)
    if request.method == "POST":
          if 'username' in request.form:
                user_to_edit.username = request.form.get('username')
          if 'roles' in request.form:
                user_to_edit.roles = request.form.get('roles')
          if 'us_phone_number' in request.form:
                user_to_edit.us_phone_number = request.form.get('us_phone_number')
          if 'availability' in request.form and len(request.form['availability'])>0:
                user_to_edit.availability = parse_dates(str(request.form.getlist('availability')).replace("['", "").replace("']", "").split(','))
          if 'email' in request.form:
                user_to_edit.email = request.form.get('email')
          if 'biography' in request.form:
                user_to_edit.biography = request.form.get('biography')
          if 'profile_picture' in request.files:
                profile_picture = request.files['profile_picture']
                if allowed_file(profile_picture.filename):
                    filename = secure_filename(profile_picture.filename)
                    profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))
                    user_to_edit.profile_picture = os.path.join(app.config['UPLOAD_FOLDER'],filename)

          user_to_edit.save()
          ret = {"access_token": guard.encode_jwt_token(user_to_edit, override_access_lifespan=None, override_refresh_lifespan=None, bypass_user_check=False, is_registration_token=False, is_reset_token=False, username=user_to_edit.username)}
          return jsonify(ret)
    if request.method == "DELETE":
        for session in user_to_edit.session:
            tutor_sessions = []
            if "tutor" in user_to_edit.rolenames:
                tutor_sessions = TutoringSession.objects(tutor__id=user_to_edit.id).all()
            if "student" in user_to_edit.rolenames:
                tutor_sessions = TutoringSession.objects(student__id=user_to_edit.id).all()
            for session in tutor_sessions:
                session.delete()
        user_to_edit.delete()
        return 'Success', 200
    if request.method == "GET":
        return user_to_edit.to_json()


@app.route('/user/students', methods=['GET'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def student_all():
    students = User.objects(roles__contains='student').all()
    return students.to_json()

@app.route('/user', methods=['GET'])
@cross_origin(supports_credentials=True)
def user_all():
    users = User.objects().all()
    return users.to_json()


@app.route('/user/tutors', methods=['GET'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def tutor_all():
    tutors = User.objects(roles__contains='tutor').all()
    return tutors.to_json()

@app.route('/subjects/new', methods=['POST'])
@cross_origin(supports_credentials=True)
def new_subject():
    subject = Subject()
    subject.subject = request.json['subject']
    subject.save()
    return subject.to_json()
    
@app.route('/subjects', methods=['GET'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def find_subjects():
  return Subject.objects().all().to_json()
    
@app.route('/subjects/delete/<id>', methods=['POST'])
@cross_origin(supports_credentials=True)
@flask_praetorian.auth_required
def delete_subject(id):
  subject = Subject.objects().get(id=id)
  print(subject)
  subject.delete()
  return ("Success", 200)
    

@app.route('/user/<username>/tutoring_history', methods=['GET'])
@cross_origin(supports_credentials=True)
def tutoring_history(username):
    try:
        user = User.objects.get(username=username)
        sessions = TutoringSession.objects(tutor__id=user.id).all()

        if(request.args.get('hours')):
            total = 0
            subjectMap = {
                    "Chemistry": 0,
                    "Physics": 0,
                    "Computer Science": 0,
                    "History": 0,
                    "Math": 0,
                    "Biology": 0,
                    "English": 0,
            }
            for session in sessions:
                if session.subject:
                    subjectMap[session.subject]+=session.lengthInHours()

            return subjectMap
        else:
            return sessions.to_json()
    except Exception as e:
        traceback.print_exc()
        return 'Failure retrieving resources', 400

@socketio.on('msg')
def handle_message(msg):
    print("Got a msg")
    socketio.emit('msg', msg)  

@socketio.on('connect')
def connect():
    print("Connected to server") 

if __name__ == '__main__':
    port = int(os.getenv('PORT'))
    socketio.run(app=app, use_reloader=True, port=5000, host="0.0.0.0")
