import logging
import os
import re
import time
import urllib

from flask import current_app as app, render_template, request, redirect, url_for, session, Blueprint, jsonify
from itsdangerous import TimedSerializer, BadTimeSignature, Signer, BadSignature
from passlib.hash import bcrypt_sha256

from CTFd.utils import sha512, is_safe_url, authed, can_send_mail, sendmail, can_register, get_config, verify_email
from CTFd.models import db, Students

auth = Blueprint('auth', __name__)


@auth.route('/confirm', methods=['POST', 'GET'])
@auth.route('/confirm/<data>', methods=['GET'])
def confirm_user(data=None):
    if not get_config('verify_emails'):
        return redirect(url_for('challenges.challenges_view'))
    if data and request.method == "GET": # User is confirming email account
        try:
            s = Signer(app.config['SECRET_KEY'])
            email = s.unsign(urllib.unquote_plus(data.decode('base64')))
        except BadSignature:
            return render_template('confirm.html', errors=['Your confirmation link seems wrong'])
        except:
            return render_template('confirm.html', errors=['Your link appears broken, please try again.'])
        team = Students.query.filter_by(email=email).first_or_404()
        team.verified = True
        db.session.commit()
        db.session.close()
        logger = logging.getLogger('regs')
        logger.warn("[{0}] {1} confirmed {2}".format(time.strftime("%m/%d/%Y %X"), team.name.encode('utf-8'), team.email.encode('utf-8')))
        if authed():
            return redirect(url_for('challenges.challenges_view'))
        return redirect(url_for('auth.login'))
    if not data and request.method == "GET": # User has been directed to the confirm page because his account is not verified
        if not authed():
            return redirect(url_for('auth.login'))
        team = Students.query.filter_by(id=session['id']).first_or_404()
        if team.verified:
            return redirect(url_for('views.profile'))
        else:
            verify_email(team.email)
        return render_template('confirm.html', team=team)


@auth.route('/reset_password', methods=['POST', 'GET'])
@auth.route('/reset_password/<data>', methods=['POST', 'GET'])
def reset_password(data=None):
    if data is not None and request.method == "GET":
        return render_template('reset_password.html', mode='set')
    if data is not None and request.method == "POST":
        try:
            s = TimedSerializer(app.config['SECRET_KEY'])
            name = s.loads(urllib.unquote_plus(data.decode('base64')), max_age=1800)
        except BadTimeSignature:
            return render_template('reset_password.html', errors=['Your link has expired'])
        except:
            return render_template('reset_password.html', errors=['Your link appears broken, please try again.'])
        team = Students.query.filter_by(name=name).first_or_404()
        team.password = bcrypt_sha256.encrypt(request.form['password'].strip())
        db.session.commit()
        db.session.close()
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        email = request.form['email'].strip()
        team = Students.query.filter_by(email=email).first()
        if not team:
            return render_template('reset_password.html', errors=['If that account exists you will receive an email, please check your inbox'])
        s = TimedSerializer(app.config['SECRET_KEY'])
        token = s.dumps(team.name)
        text = """
Did you initiate a password reset?

{0}/{1}

""".format(url_for('auth.reset_password', _external=True), urllib.quote_plus(token.encode('base64')))

        sendmail(email, text)

        return render_template('reset_password.html', errors=['If that account exists you will receive an email, please check your inbox'])
    return render_template('reset_password.html')


@auth.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        errors = []
        name = request.form['name']
        student = Students.query.filter_by(name=name).first()
        if student:
            if student and bcrypt_sha256.verify(request.form['password'], student.password):
                try:
                    session.regenerate() # NO SESSION FIXATION FOR YOU
                except:
                    pass # TODO: Some session objects don't implement regenerate :(

                session['username'] = student.name
                session['id'] = student.id
                session['admin'] = student.admin
                session['nonce'] = sha512(os.urandom(10))
                db.session.close()

                logger = logging.getLogger('logins')
                logger.warn("[{0}] {1} logged in".format(time.strftime("%m/%d/%Y %X"), session['username'].encode('utf-8')))

                if request.args.get('next') and is_safe_url(request.args.get('next')):
                    return redirect(request.args.get('next'))
                return redirect(url_for('challenges.challenges_view'))
            else: # This user exists but the password is wrong
                errors.append("Your username or password is incorrect")
                db.session.close()
                return render_template('login.html', errors=errors)
        else:  # This user just doesn't exist
            errors.append("Your username or password is incorrect")
            db.session.close()
            return render_template('login.html', errors=errors)
    else:
        db.session.close()
        return render_template('login.html')

@auth.route('/loginAndroid', methods=['POST'])
def loginAndroid():
    errors = []
    name = request.form['name']
    student = Students.query.filter_by(name=name).first()
    if student:
        if student and bcrypt_sha256.verify(request.form['password'], student.password):
            try:
                session.regenerate() # NO SESSION FIXATION FOR YOU
            except:
                pass # TODO: Some session objects don't implement regenerate :(
            session['username'] = student.name
            session['id'] = student.id
            session['admin'] = student.admin
            session['nonce'] = sha512(os.urandom(10))
            session.modified = True
            db.session.close()

            logger = logging.getLogger('logins')
            logger.warn("[{0}] {1} logged in".format(time.strftime("%m/%d/%Y %X"), session['username'].encode('utf-8')))

            if request.args.get('next') and is_safe_url(request.args.get('next')):
                return redirect(request.args.get('next'))
            return jsonify({'status': '200', 'nonce': session['nonce']})
        else: # This user exists but the password is wrong
            errors.append("Your username or password is incorrect")
            db.session.close()
            return jsonify({'status': '400', 'message': 'Invalid Login'})
    else:  # This user just doesn't exist
        errors.append("Your username or password is incorrect")
        db.session.close()
        return render_template('login.html', errors=errors)


@auth.route('/logout')
def logout():
    if authed():
        session.clear()
    return redirect(url_for('views.static_html'))
