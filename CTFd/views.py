import os
import re

from flask import current_app as app, render_template, request, redirect, abort, jsonify, url_for, session, Blueprint, Response, send_file
from jinja2.exceptions import TemplateNotFound
from passlib.hash import bcrypt_sha256
from sqlalchemy import union_all

from CTFd.utils import authed, is_setup, validate_url, get_config, set_config, sha512, cache, ctftime, view_after_ctf, ctf_started, \
    is_admin
from CTFd.models import db, Students, Solves, Awards, Files, Pages, Teams, Challenges

views = Blueprint('views', __name__)


@views.before_request
def redirect_setup():
    if request.path.startswith("/static"):
        return
    if not is_setup() and request.path != "/setup":
        return redirect(url_for('views.setup'))


@views.route('/setup', methods=['GET', 'POST'])
def setup():
    # with app.app_context():
        # admin = Teams.query.filter_by(admin=True).first()

    if not is_setup():
        if not session.get('nonce'):
            session['nonce'] = sha512(os.urandom(10))
        if request.method == 'POST':
            ctf_name = request.form['ctf_name']
            ctf_name = set_config('ctf_name', ctf_name)

            # CSS
            css = set_config('start', '')

            # Admin user
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            admin = Students(name, email, password, 1)
            admin.admin = True
            admin.banned = True

            # Index page
            page = Pages('index', """<div class="container main-container">
    <img class="logo" src="{0}/static/original/img/logo.png" />
    <h3 class="text-center">
        Welcome to a cool CTF framework written by <a href="https://github.com/ColdHeat">Kevin Chung</a> of <a href="https://github.com/isislab">@isislab</a>
    </h3>

    <h4 class="text-center">
        <a href="{0}/admin">Click here</a> to login and setup your CTF
    </h4>
</div>""".format(request.script_root))

            # max attempts per challenge
            max_tries = set_config("max_tries", 0)

            # Start time
            start = set_config('start', None)
            end = set_config('end', None)

            # Challenges cannot be viewed by unregistered users
            view_challenges_unregistered = set_config('view_challenges_unregistered', None)

            # Allow/Disallow registration
            prevent_registration = set_config('prevent_registration', None)

            # Verify emails
            verify_emails = set_config('verify_emails', None)

            mail_server = set_config('mail_server', None)
            mail_port = set_config('mail_port', None)
            mail_tls = set_config('mail_tls', None)
            mail_ssl = set_config('mail_ssl', None)
            mail_username = set_config('mail_username', None)
            mail_password = set_config('mail_password', None)

            setup = set_config('setup', True)

            db.session.add(page)
            db.session.add(admin)
            db.session.commit()
            db.session.close()
            app.setup = False
            with app.app_context():
                cache.clear()
            return redirect(url_for('views.static_html'))
        return render_template('setup.html', nonce=session.get('nonce'))
    return redirect(url_for('views.static_html'))


# Custom CSS handler
@views.route('/static/user.css')
def custom_css():
    return Response(get_config("css"), mimetype='text/css')


# Static HTML files
@views.route("/", defaults={'template': 'index'})
@views.route("/<template>")
def static_html(template):
    try:
        return render_template('%s.html' % template)
    except TemplateNotFound:
        page = Pages.query.filter_by(route=template).first_or_404()
        return render_template('page.html', content=page.html)


@views.route('/students', defaults={'page': '1'})
@views.route('/students/<int:page>')
def students(page):
    page = abs(int(page))
    results_per_page = 50
    page_start = results_per_page * (page - 1)
    page_end = results_per_page * (page - 1) + results_per_page

    if get_config('verify_emails'):
        count = Students.query.filter_by(verified=True, banned=False).count()
        students = Students.query.filter_by(verified=True, banned=False).slice(page_start, page_end).all()
    else:
        count = Students.query.filter_by(banned=False).count()
        students = Students.query.filter_by(banned=False).slice(page_start, page_end).all()
    pages = int(count / results_per_page) + (count % results_per_page > 0)
    return render_template('students.html', students=students, student_pages=pages, curr_page=page)


@views.route('/student/<int:studentid>', methods=['GET', 'POST'])
def student(studentid):
    if get_config('view_scoreboard_if_authed') and not authed():
        return redirect(url_for('auth.login', next=request.path))
    user = Students.query.filter_by(id=studentid).first_or_404()
    solves = Solves.query.filter_by(studentid=studentid)
    awards = Awards.query.filter_by(studentid=studentid).all()
    score = user.score()
    place = user.place()
    db.session.close()

    if request.method == 'GET':
        return render_template('student.html', solves=solves, awards=awards, student=user, score=score, place=place)
    elif request.method == 'POST':
        json = {'solves': []}
        for x in solves:
            json['solves'].append({'id': x.id, 'chal': x.chalid, 'student': x.studentid})
        return jsonify(json)


@views.route('/profile', methods=['POST', 'GET'])
def profile():
    if authed():
        if request.method == "POST":
            errors = []

            name = request.form.get('name')
            email = request.form.get('email')

            user = Students.query.filter_by(id=session['id']).first()

            if not get_config('prevent_name_change'):
                names = Students.query.filter_by(name=name).first()
                name_len = len(request.form['name']) == 0

            emails = Students.query.filter_by(email=email).first()
            valid_email = re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email)

            if ('password' in request.form.keys() and not len(request.form['password']) == 0) and \
                    (not bcrypt_sha256.verify(request.form.get('confirm').strip(), user.password)):
                errors.append("Your old password doesn't match what we have.")
            if not valid_email:
                errors.append("That email doesn't look right")
            if not get_config('prevent_name_change') and names and name != session['username']:
                errors.append('That student name is already taken')
            if emails and emails.id != session['id']:
                errors.append('That email has already been used')
            if not get_config('prevent_name_change') and name_len:
                errors.append('Pick a longer student name')

            if len(errors) > 0:
                return render_template('profile.html', name=name, email=email, errors=errors)
            else:
                student = Students.query.filter_by(id=session['id']).first()
                if not get_config('prevent_name_change'):
                    student.name = name
                if student.email != email.lower():
                    student.email = email.lower()
                    if get_config('verify_emails'):
                        student.verified = False
                session['username'] = student.name

                if 'password' in request.form.keys() and not len(request.form['password']) == 0:
                    student.password = bcrypt_sha256.encrypt(request.form.get('password'))
                db.session.commit()
                db.session.close()
                return redirect(url_for('views.profile'))
        else:
            user = Students.query.filter_by(id=session['id']).first()
            name = user.name
            email = user.email
            prevent_name_change = get_config('prevent_name_change')
            confirm_email = get_config('verify_emails') and not user.verified
            return render_template('profile.html', name=name, email=email, prevent_name_change=prevent_name_change,
                                   confirm_email=confirm_email)
    else:
        return redirect(url_for('auth.login'))


@views.route('/files', defaults={'path': ''})
@views.route('/files/<path:path>')
def file_handler(path):
    f = Files.query.filter_by(location=path).first_or_404()
    if f.chal:
        if not is_admin():
            if not ctftime():
                if view_after_ctf() and ctf_started():
                    pass
                else:
                    abort(403)
    return send_file(os.path.join(app.root_path, 'uploads', f.location))

@views.route('/teams', defaults={'page': '1'})
@views.route('/teams/<int:page>')
def teams(page):
    page = abs(int(page))
    results_per_page = 50
    page_start = results_per_page * (page - 1)
    page_end = results_per_page * (page - 1) + results_per_page

    count = Teams.query.filter_by().count()
    teams = Teams.query.filter_by().slice(page_start, page_end).all()

    pages = int(count / results_per_page) + (count % results_per_page > 0)
    return render_template('teams.html', teams=teams, team_pages=pages, curr_page=page)

@views.route('/team/<int:teamid>')
def team(teamid):
    if get_config('view_scoreboard_if_authed') and not authed():
        return redirect(url_for('auth.login', next=request.path))
    team = Teams.query.filter_by(id=teamid)
    students = Students.query.filter_by(teamid=teamid)
    # get solves data by team id
    # get awards data by team id
    db.session.close()
    if request.method == 'GET':
        return render_template('team.html', team=team, students=students)
    elif request.method == 'POST':
        return None # return solves data by team id

@views.route('/team/<int:teamid>/challenges')
def teamChallenges(teamid):
    team = Teams.query.filter_by(id=teamid).first()
    challenges = team.challenges()
    return render_template('tChallenges.html', team=team, challenges=challenges)

@views.route('/team/<int:teamid>/solves')
def teamSolves(teamid):
    team = Teams.query.filter_by(id=teamid).first()
    solves = team.solves()
    return render_template('tSolves.html', team=team, solves=solves)

@views.route('/test')
def test():
    score = db.func.sum(Challenges.value).label('score')
    date = db.func.max(Solves.date).label('date')
    scores = db.session.query(Solves.studentid.label('studentid'), score, date).join(Challenges).group_by(
        Solves.studentid)
    awards = db.session.query(Awards.studentid.label('studentid'), db.func.sum(Awards.value).label('score'),
                              db.func.max(Awards.date).label('date')) \
        .group_by(Awards.studentid)
    res = db.session.query(union_all(scores, awards).alias('results')).all()

    results = union_all(scores, awards).alias('results')

    sum = db.session.query(results.columns.studentid, db.func.sum(results.columns.score).label('score'),
                                 db.func.max(results.columns.date).label('date')) \
        .group_by(results.columns.studentid).all()
    sumscores = db.session.query(results.columns.studentid, db.func.sum(results.columns.score).label('score'),
                                 db.func.max(results.columns.date).label('date')) \
        .group_by(results.columns.studentid).subquery()
    teams = db.session.query(Teams.id.label('teamid'), Teams.name.label('name'),
                             db.func.sum(sumscores.columns.score).label('score'),
                             db.func.max(sumscores.columns.date).label('date')).join(Students) \
        .filter(Students.id == sumscores.columns.studentid, Students.teamid == Teams.id) \
        .group_by(Teams.id).all()


    return render_template('test.html', scores=scores, awards=awards, results=res, sumscores=sum, teams=teams)
