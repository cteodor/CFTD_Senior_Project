import hashlib
import json
import os

from flask import current_app as app, render_template, request, redirect, jsonify, url_for, Blueprint, session
from flask import flash
from passlib.hash import bcrypt_sha256
from sqlalchemy.sql import not_

from CTFd.utils import admins_only, is_admin, unix_time, get_config, \
    set_config, sendmail, rmdir, create_image, delete_image, run_image, container_status, container_ports, \
    container_stop, container_start, get_themes, cache, upload_file, authed, create_section_students_from_file, \
    generate_password
from CTFd.models import db, Students, Solves, Awards, Containers, Challenges, WrongKeys, Keys, Tags, Files, Tracking, \
    Pages, Config, DatabaseError, \
    Sections, Teams
from CTFd.scoreboard import get_standings

admin = Blueprint('admin', __name__)


@admin.route('/admin', methods=['GET'])
def admin_view():
    if is_admin():
        return redirect(url_for('admin.admin_graphs'))

    return redirect(url_for('auth.login'))


@admin.route('/admin/section/<int:sectionid>', methods=['PUT'])
@admins_only
def set_section(sectionid):
    user = Students.query.filter_by(admin=True).first()
    user.sectionid = sectionid
    db.session.commit()
    db.session.close()
    return str(sectionid)


@admin.route('/admin/section', methods=['GET'])
@admins_only
def get_section():
    user = Students.query.filter_by(admin=True).first()
    sectionid = user.sectionid
    return str(sectionid)


@admin.route('/admin/section/new', methods=['POST', 'GET'])
@admins_only
def new_section_from_file():
    if request.method == 'GET':
        return render_template('admin/new_section.html')
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            students = create_section_students_from_file(file)
    return render_template("admin/success.html", students=students)


@admin.route('/admin/sections', methods=['GET'])
@admins_only
def get_sections():
    sections = Sections.query.all()

    section_list = []
    for section in sections:
        section_list.append({
            'sectionNumber': section.sectionNumber,
            'courseNumber': section.courseNumber
        })
    json_data = {'sections': section_list}
    return jsonify(json_data)


@admin.route('/admin/graphs')
@admins_only
def admin_graphs():
    return render_template('admin/graphs.html')


@admin.route('/admin/config', methods=['GET', 'POST'])
@admins_only
def admin_config():
    if request.method == "POST":
        start = None
        end = None
        if request.form.get('start'):
            start = int(request.form['start'])
        if request.form.get('end'):
            end = int(request.form['end'])

        try:
            view_challenges_unregistered = bool(request.form.get('view_challenges_unregistered', None))
            view_scoreboard_if_authed = bool(request.form.get('view_scoreboard_if_authed', None))
            prevent_registration = bool(request.form.get('prevent_registration', None))
            prevent_name_change = bool(request.form.get('prevent_name_change', None))
            view_after_ctf = bool(request.form.get('view_after_ctf', None))
            verify_emails = bool(request.form.get('verify_emails', None))
            mail_tls = bool(request.form.get('mail_tls', None))
            mail_ssl = bool(request.form.get('mail_ssl', None))
        except (ValueError, TypeError):
            view_challenges_unregistered = None
            view_scoreboard_if_authed = None
            prevent_registration = None
            prevent_name_change = None
            view_after_ctf = None
            verify_emails = None
            mail_tls = None
            mail_ssl = None
        finally:
            view_challenges_unregistered = set_config('view_challenges_unregistered', view_challenges_unregistered)
            view_scoreboard_if_authed = set_config('view_scoreboard_if_authed', view_scoreboard_if_authed)
            prevent_registration = set_config('prevent_registration', prevent_registration)
            prevent_name_change = set_config('prevent_name_change', prevent_name_change)
            view_after_ctf = set_config('view_after_ctf', view_after_ctf)
            verify_emails = set_config('verify_emails', verify_emails)
            mail_tls = set_config('mail_tls', mail_tls)
            mail_ssl = set_config('mail_ssl', mail_ssl)

        mail_server = set_config("mail_server", request.form.get('mail_server', None))
        mail_port = set_config("mail_port", request.form.get('mail_port', None))

        mail_username = set_config("mail_username", request.form.get('mail_username', None))
        mail_password = set_config("mail_password", request.form.get('mail_password', None))

        ctf_name = set_config("ctf_name", request.form.get('ctf_name', None))
        ctf_theme = set_config("ctf_theme", request.form.get('ctf_theme', None))

        mailfrom_addr = set_config("mailfrom_addr", request.form.get('mailfrom_addr', None))
        mg_base_url = set_config("mg_base_url", request.form.get('mg_base_url', None))
        mg_api_key = set_config("mg_api_key", request.form.get('mg_api_key', None))

        max_tries = set_config("max_tries", request.form.get('max_tries', None))

        db_start = Config.query.filter_by(key='start').first()
        db_start.value = start

        db_end = Config.query.filter_by(key='end').first()
        db_end.value = end

        db.session.add(db_start)
        db.session.add(db_end)

        db.session.commit()
        db.session.close()
        with app.app_context():
            cache.clear()
        return redirect(url_for('admin.admin_config'))

    with app.app_context():
        cache.clear()
    ctf_name = get_config('ctf_name')
    ctf_theme = get_config('ctf_theme')
    max_tries = get_config('max_tries')

    mail_server = get_config('mail_server')
    mail_port = get_config('mail_port')
    mail_username = get_config('mail_username')
    mail_password = get_config('mail_password')

    mailfrom_addr = get_config('mailfrom_addr')
    mg_api_key = get_config('mg_api_key')
    mg_base_url = get_config('mg_base_url')
    if not max_tries:
        set_config('max_tries', 0)
        max_tries = 0

    view_after_ctf = get_config('view_after_ctf')
    start = get_config('start')
    end = get_config('end')

    mail_tls = get_config('mail_tls')
    mail_ssl = get_config('mail_ssl')

    view_challenges_unregistered = get_config('view_challenges_unregistered')
    view_scoreboard_if_authed = get_config('view_scoreboard_if_authed')
    prevent_registration = get_config('prevent_registration')
    prevent_name_change = get_config('prevent_name_change')
    verify_emails = get_config('verify_emails')

    db.session.commit()
    db.session.close()

    themes = get_themes()
    themes.remove(ctf_theme)

    return render_template('admin/config.html',
                           ctf_name=ctf_name,
                           ctf_theme_config=ctf_theme,
                           start=start,
                           end=end,
                           max_tries=max_tries,
                           mail_server=mail_server,
                           mail_port=mail_port,
                           mail_username=mail_username,
                           mail_password=mail_password,
                           mail_tls=mail_tls,
                           mail_ssl=mail_ssl,
                           view_challenges_unregistered=view_challenges_unregistered,
                           view_scoreboard_if_authed=view_scoreboard_if_authed,
                           prevent_registration=prevent_registration,
                           mailfrom_addr=mailfrom_addr,
                           mg_base_url=mg_base_url,
                           mg_api_key=mg_api_key,
                           prevent_name_change=prevent_name_change,
                           verify_emails=verify_emails,
                           view_after_ctf=view_after_ctf,
                           themes=themes)


@admin.route('/admin/css', methods=['GET', 'POST'])
@admins_only
def admin_css():
    if request.method == 'POST':
        css = request.form['css']
        css = set_config('css', css)
        with app.app_context():
            cache.clear()
        return '1'
    return '0'


@admin.route('/admin/pages', defaults={'route': None}, methods=['GET', 'POST'])
@admin.route('/admin/pages/<route>', methods=['GET', 'POST'])
@admins_only
def admin_pages(route):
    if request.method == 'GET' and request.args.get('mode') == 'create':
        return render_template('admin/editor.html')
    if route and request.method == 'GET':
        page = Pages.query.filter_by(route=route).first()
        return render_template('admin/editor.html', page=page)
    if route and request.method == 'POST':
        page = Pages.query.filter_by(route=route).first()
        errors = []
        html = request.form['html']
        route = request.form['route']
        if not route:
            errors.append('Missing URL route')
        if errors:
            page = Pages(html, '')
            return render_template('/admin/editor.html', page=page)
        if page:
            page.route = route
            page.html = html
            db.session.commit()
            db.session.close()
            return redirect(url_for('admin.admin_pages'))
        page = Pages(route, html)
        db.session.add(page)
        db.session.commit()
        db.session.close()
        return redirect(url_for('admin.admin_pages'))
    pages = Pages.query.all()
    return render_template('admin/pages.html', routes=pages, css=get_config('css'))


@admin.route('/admin/page/<pageroute>/delete', methods=['POST'])
@admins_only
def delete_page(pageroute):
    page = Pages.query.filter_by(route=pageroute).first_or_404()
    db.session.delete(page)
    db.session.commit()
    db.session.close()
    return '1'


@admin.route('/admin/containers', methods=['GET'])
@admins_only
def list_container():
    containers = Containers.query.all()
    for c in containers:
        c.status = container_status(c.name)
        c.ports = ', '.join(container_ports(c.name, verbose=True))
    return render_template('admin/containers.html', containers=containers)


@admin.route('/admin/containers/<int:container_id>/stop', methods=['POST'])
@admins_only
def stop_container(container_id):
    container = Containers.query.filter_by(id=container_id).first_or_404()
    if container_stop(container.name):
        return '1'
    else:
        return '0'


@admin.route('/admin/containers/<int:container_id>/start', methods=['POST'])
@admins_only
def run_container(container_id):
    container = Containers.query.filter_by(id=container_id).first_or_404()
    if container_status(container.name) == 'missing':
        if run_image(container.name):
            return '1'
        else:
            return '0'
    else:
        if container_start(container.name):
            return '1'
        else:
            return '0'


@admin.route('/admin/containers/<int:container_id>/delete', methods=['POST'])
@admins_only
def delete_container(container_id):
    container = Containers.query.filter_by(id=container_id).first_or_404()
    if delete_image(container.name):
        db.session.delete(container)
        db.session.commit()
        db.session.close()
    return '1'


@admin.route('/admin/containers/new', methods=['POST'])
@admins_only
def new_container():
    name = request.form.get('name')
    if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_'):
        return redirect(url_for('admin.list_container'))
    buildfile = request.form.get('buildfile')
    files = request.files.getlist('files[]')
    create_image(name=name, buildfile=buildfile, files=files)
    run_image(name)
    return redirect(url_for('admin.list_container'))


@admin.route('/admin/chals', methods=['POST', 'GET'])
@admins_only
def admin_chals():
    if request.method == 'POST':
        chals = Challenges.query.add_columns('id', 'name', 'value', 'description', 'category', 'hidden', 'level', 'prereq').order_by(
            Challenges.level).all()

        students_with_points = db.session.query(Solves.studentid).join(Students).filter(
            Students.banned == False).group_by(Solves.studentid).count()

        json_data = {'game': []}
        for x in chals:
            solve_count = Solves.query.join(Students, Solves.studentid == Students.id).filter(
                Solves.chalid == x[1], Students.banned == False).count()
            if students_with_points > 0:
                percentage = (float(solve_count) / float(students_with_points))
            else:
                percentage = 0.0
            prereq = Challenges.query.filter(Challenges.id == x.prereq).first()
            if prereq is None:
                prereq_name = ""
            else:
                prereq_name = prereq.name
            json_data['game'].append({
                'id': x.id,
                'name': x.name,
                'value': x.value,
                'description': x.description,
                'category': x.category,
                'hidden': x.hidden,
                'percentage_solved': percentage,
                'prereq': prereq_name,
                'level': x.level
            })

        db.session.close()
        return jsonify(json_data)
    else:
        return render_template('admin/chals.html')


@admin.route('/admin/keys/<int:chalid>', methods=['POST', 'GET'])
@admins_only
def admin_keys(chalid):
    chal = Challenges.query.filter_by(id=chalid).first_or_404()

    if request.method == 'GET':
        json_data = {'keys': []}
        flags = json.loads(chal.flags)
        for i, x in enumerate(flags):
            json_data['keys'].append({'id': i, 'key': x['flag'], 'type': x['type']})
        return jsonify(json_data)
    elif request.method == 'POST':
        newkeys = request.form.getlist('keys[]')
        newvals = request.form.getlist('vals[]')
        flags = []
        for flag, val in zip(newkeys, newvals):
            flag_dict = {'flag': flag, 'type': int(val)}
            flags.append(flag_dict)
        json_data = json.dumps(flags)

        chal.flags = json_data

        db.session.commit()
        db.session.close()
        return '1'


@admin.route('/admin/tags/<int:chalid>', methods=['GET', 'POST'])
@admins_only
def admin_tags(chalid):
    if request.method == 'GET':
        tags = Tags.query.filter_by(chal=chalid).all()
        json_data = {'tags': []}
        for x in tags:
            json_data['tags'].append({'id': x.id, 'chal': x.chal, 'tag': x.tag})
        return jsonify(json_data)

    elif request.method == 'POST':
        newtags = request.form.getlist('tags[]')
        for x in newtags:
            tag = Tags(chalid, x)
            db.session.add(tag)
        db.session.commit()
        db.session.close()
        return '1'


@admin.route('/admin/tags/<int:tagid>/delete', methods=['POST'])
@admins_only
def admin_delete_tags(tagid):
    if request.method == 'POST':
        tag = Tags.query.filter_by(id=tagid).first_or_404()
        db.session.delete(tag)
        db.session.commit()
        db.session.close()
        return '1'


@admin.route('/admin/files/<int:chalid>', methods=['GET', 'POST'])
@admins_only
def admin_files(chalid):
    if request.method == 'GET':
        files = Files.query.filter_by(chal=chalid).all()
        json_data = {'files': []}
        for x in files:
            json_data['files'].append({'id': x.id, 'file': x.location})
        return jsonify(json_data)
    if request.method == 'POST':
        if request.form['method'] == "delete":
            f = Files.query.filter_by(id=request.form['file']).first_or_404()
            if os.path.exists(os.path.join(app.root_path, 'uploads',
                                           f.location)):  # Some kind of os.path.isfile issue on Windows...
                os.unlink(os.path.join(app.root_path, 'uploads', f.location))
            db.session.delete(f)
            db.session.commit()
            db.session.close()
            return '1'
        elif request.form['method'] == "upload":
            files = request.files.getlist('files[]')

            for f in files:
                upload_file(file=f, chalid=chalid)

            db.session.commit()
            db.session.close()
            return redirect(url_for('admin.admin_chals'))


@admin.route('/admin/students', defaults={'page': '1'})
@admin.route('/admin/students/<int:page>')
@admins_only
def admin_students(page):
    page = abs(int(page))
    results_per_page = 50
    page_start = results_per_page * (page - 1)
    page_end = results_per_page * (page - 1) + results_per_page

    admin = Students.query.filter_by(id=session['id']).first()

    students = Students.query.filter_by(sectionid=admin.sectionid).order_by(Students.id.asc()).slice(page_start,
                                                                                                     page_end).all()
    count = db.session.query(db.func.count(Students.id)).filter_by(sectionid=admin.sectionid).first()[0]
    pages = int(count / results_per_page) + (count % results_per_page > 0)
    return render_template('admin/students.html', students=students, pages=pages, curr_page=page)


@admin.route('/admin/student/<int:studentid>', methods=['GET', 'POST'])
@admins_only
def admin_student(studentid):
    user = Students.query.filter_by(id=studentid).first_or_404()
    admin = Students.query.filter_by(id=session['id']).first()

    if admin.sectionid != user.sectionid:
        return render_template('admin/wrong_section.html', section=user.sectionid)

    if request.method == 'GET':
        solves = Solves.query.filter_by(studentid=studentid).all()
        solve_ids = [s.chalid for s in solves]
        missing = Challenges.query.filter(not_(Challenges.id.in_(solve_ids))).all()

        wrong_keys = WrongKeys.query.filter_by(studentid=studentid).order_by(WrongKeys.date.asc()).all()
        awards = Awards.query.filter_by(studentid=studentid).order_by(Awards.date.asc()).all()
        score = user.score()
        place = user.place()
        return render_template('admin/student.html', solves=solves, student=user, score=score,
                               missing=missing,
                               place=place, wrong_keys=wrong_keys, awards=awards)
    elif request.method == 'POST':
        admin_user = request.form.get('admin', None)
        if admin_user:
            admin_user = True if admin_user == 'true' else False
            user.admin = admin_user
            # Set user.banned to hide admins from scoreboard
            user.banned = admin_user
            db.session.commit()
            db.session.close()
            return jsonify({'data': ['success']})

        verified = request.form.get('verified', None)
        if verified:
            verified = True if verified == 'true' else False
            user.verified = verified
            db.session.commit()
            db.session.close()
            return jsonify({'data': ['success']})

        name = request.form.get('name', None)
        password = request.form.get('password', None)
        email = request.form.get('email', None)
        website = request.form.get('website', None)
        affiliation = request.form.get('affiliation', None)
        country = request.form.get('country', None)

        errors = []

        name_used = Students.query.filter(Students.name == name).first()
        if name_used and int(name_used.id) != int(studentid):
            errors.append('That name is taken')

        email_used = Students.query.filter(Students.email == email).first()
        if email_used and int(email_used.id) != int(studentid):
            errors.append('That email is taken')

        if errors:
            db.session.close()
            return jsonify({'data': errors})
        else:
            user.name = name
            user.email = email
            if password:
                user.password = bcrypt_sha256.encrypt(password)
            user.website = website
            user.affiliation = affiliation
            user.country = country
            db.session.commit()
            db.session.close()
            return jsonify({'data': ['success']})


@admin.route('/admin/student/<int:studentid>/mail', methods=['POST'])
@admins_only
def email_user(studentid):
    message = request.form.get('msg', None)
    student = Students.query.filter(Students.id == studentid).first()
    if message and student:
        if sendmail(student.email, message):
            return '1'
    return '0'


@admin.route('/admin/student/<int:studentid>/ban', methods=['POST'])
@admins_only
def ban(studentid):
    user = Students.query.filter_by(id=studentid).first_or_404()
    user.banned = True
    db.session.commit()
    db.session.close()
    return redirect(url_for('admin.admin_scoreboard'))


@admin.route('/admin/student/<int:studentid>/unban', methods=['POST'])
@admins_only
def unban(studentid):
    user = Students.query.filter_by(id=studentid).first_or_404()
    user.banned = False
    db.session.commit()
    db.session.close()
    return redirect(url_for('admin.admin_scoreboard'))


@admin.route('/admin/student/<int:studentid>/delete', methods=['POST'])
@admins_only
def delete_student(studentid):
    try:
        WrongKeys.query.filter_by(studentid=studentid).delete()
        Solves.query.filter_by(studentid=studentid).delete()
        Tracking.query.filter_by(student=studentid).delete()
        Students.query.filter_by(id=studentid).delete()
        db.session.commit()
        db.session.close()
    except DatabaseError:
        return '0'
    else:
        return '1'


@admin.route('/admin/student/new', methods=['POST'])
@admins_only
def add_student():
    password = generate_password()
    student = Students(request.form['name'], request.form['email'], password, int(request.form['team']), int(request.form['section']))
    student.verified = True
    db.session.add(student)
    db.session.commit()
    db.session.close()
    students = list()
    students.append({"name": request.form['name'], "password": password})
    return render_template('admin/success.html', students=students)


@admin.route('/admin/graphs/<graph_type>')
@admins_only
def admin_graph(graph_type):
    if graph_type == 'categories':
        categories = db.session.query(Challenges.category, db.func.count(Challenges.category)).group_by(
            Challenges.category).all()
        json_data = {'categories': []}
        for category, count in categories:
            json_data['categories'].append({'category': category, 'count': count})
        return jsonify(json_data)
    elif graph_type == "solves":
        solves_sub = db.session.query(Solves.chalid, db.func.count(Solves.chalid).label('solves_cnt')) \
            .join(Students, Solves.studentid == Students.id).filter(Students.banned == False, Students.sectionid == get_section()) \
            .group_by(Solves.chalid).subquery()
        solves = db.session.query(solves_sub.columns.chalid, solves_sub.columns.solves_cnt, Challenges.name) \
            .join(Challenges, solves_sub.columns.chalid == Challenges.id).all()
        json_data = {}
        for chal, count, name in solves:
            json_data[name] = count
        return jsonify(json_data)


@admin.route('/admin/scoreboard')
@admins_only
def admin_scoreboard():
    standings = get_standings(admin=True)
    return render_template('admin/scoreboard.html', teams=standings)


@admin.route('/admin/students/<int:studentid>/awards', methods=['GET'])
@admins_only
def admin_awards(studentid):
    awards = Awards.query.filter_by(studentid=studentid).all()

    awards_list = []
    for award in awards:
        awards_list.append({
            'id': award.id,
            'name': award.name,
            'description': award.description,
            'date': award.date,
            'value': award.value,
            'category': award.category,
            'icon': award.icon
        })
    json_data = {'awards': awards_list}
    return jsonify(json_data)


@admin.route('/admin/awards/add', methods=['POST'])
@admins_only
def create_award():
    try:
        studentid = request.form['studentid']
        name = request.form.get('name', 'Award')
        value = request.form.get('value', 0)
        award = Awards(studentid, name, value)
        award.description = request.form.get('description')
        award.category = request.form.get('category')
        db.session.add(award)
        db.session.commit()
        db.session.close()
        return '1'
    except Exception as e:
        print(e)
        return '0'


@admin.route('/admin/awards/<int:award_id>/delete', methods=['POST'])
@admins_only
def delete_award(award_id):
    award = Awards.query.filter_by(id=award_id).first_or_404()
    db.session.delete(award)
    db.session.commit()
    db.session.close()
    return '1'


@admin.route('/admin/scores')
@admins_only
def admin_scores():
    score = db.func.sum(Challenges.value).label('score')
    quickest = db.func.max(Solves.date).label('quickest')
    students = db.session.query(Solves.studentid, Students.name, score).join(Students).join(Challenges).filter(
        Students.banned == False).group_by(Solves.studentid).order_by(score.desc(), quickest)
    db.session.close()
    json_data = {'students': []}
    for i, x in enumerate(students):
        json_data['students'].append({'place': i + 1, 'id': x.studentid, 'name': x.name, 'score': int(x.score)})
    return jsonify(json_data)


@admin.route('/admin/solves/<studentid>', methods=['GET'])
@admins_only
def admin_solves(studentid="all"):
    if studentid == "all":
        solves = Solves.query.all()
    else:
        solves = Solves.query.filter_by(studentid=studentid).all()
        awards = Awards.query.filter_by(studentid=studentid).all()
    db.session.close()
    json_data = {'solves': []}
    for x in solves:
        json_data['solves'].append({
            'id': x.id,
            'chal': x.chal.name,
            'chalid': x.chalid,
            'student': x.studentid,
            'value': x.chal.value,
            'category': x.chal.category,
            'time': unix_time(x.date)
        })
    for award in awards:
        json_data['solves'].append({
            'chal': award.name,
            'chalid': None,
            'student': award.studentid,
            'value': award.value,
            'category': award.category,
            'time': unix_time(award.date)
        })
    json_data['solves'].sort(key=lambda k: k['time'])
    return jsonify(json_data)


@admin.route('/admin/solves/<int:studentid>/<int:chalid>/solve', methods=['POST'])
@admins_only
def create_solve(studentid, chalid):
    solve = Solves(chalid=chalid, studentid=studentid, ip='127.0.0.1', flag='MARKED_AS_SOLVED_BY_ADMIN')
    db.session.add(solve)
    db.session.commit()
    db.session.close()
    return '1'


@admin.route('/admin/solves/<int:keyid>/delete', methods=['POST'])
@admins_only
def delete_solve(keyid):
    solve = Solves.query.filter_by(id=keyid).first_or_404()
    db.session.delete(solve)
    db.session.commit()
    db.session.close()
    return '1'


@admin.route('/admin/wrong_keys/<int:keyid>/delete', methods=['POST'])
@admins_only
def delete_wrong_key(keyid):
    wrong_key = WrongKeys.query.filter_by(id=keyid).first_or_404()
    db.session.delete(wrong_key)
    db.session.commit()
    db.session.close()
    return '1'


@admin.route('/admin/statistics', methods=['GET'])
@admins_only
def admin_stats():
    students_registered = db.session.query(db.func.count(Students.id)).first()[0]
    wrong_count = db.session.query(db.func.count(WrongKeys.id)).first()[0]
    solve_count = db.session.query(db.func.count(Solves.id)).first()[0]
    challenge_count = db.session.query(db.func.count(Challenges.id)).first()[0]

    solves_sub = db.session.query(Solves.chalid, db.func.count(Solves.chalid).label('solves_cnt')) \
        .join(Students, Solves.studentid == Students.id).filter(Students.banned == False) \
        .group_by(Solves.chalid).subquery()
    solves = db.session.query(solves_sub.columns.chalid, solves_sub.columns.solves_cnt, Challenges.name) \
        .join(Challenges, solves_sub.columns.chalid == Challenges.id).all()
    solve_data = {}
    for chal, count, name in solves:
        solve_data[name] = count

    most_solved = None
    least_solved = None
    if len(solve_data):
        most_solved = max(solve_data, key=solve_data.get)
        least_solved = min(solve_data, key=solve_data.get)

    db.session.expunge_all()
    db.session.commit()
    db.session.close()

    return render_template('admin/statistics.html', student_count=students_registered,
                           wrong_count=wrong_count,
                           solve_count=solve_count,
                           challenge_count=challenge_count,
                           solve_data=solve_data,
                           most_solved=most_solved,
                           least_solved=least_solved)


@admin.route('/admin/wrong_keys', defaults={'page': '1'}, methods=['GET'])
@admin.route('/admin/wrong_keys/<int:page>', methods=['GET'])
@admins_only
def admin_wrong_key(page):
    page = abs(int(page))
    results_per_page = 50
    page_start = results_per_page * (page - 1)
    page_end = results_per_page * (page - 1) + results_per_page

    wrong_keys = WrongKeys.query.add_columns(WrongKeys.id, WrongKeys.chalid, WrongKeys.flag, WrongKeys.studentid,
                                             WrongKeys.date,
                                             Challenges.name.label('chal_name'), Students.name.label('student_name')) \
        .join(Challenges) \
        .join(Students) \
        .order_by(WrongKeys.date.desc()) \
        .slice(page_start, page_end) \
        .all()

    wrong_count = db.session.query(db.func.count(WrongKeys.id)).first()[0]
    pages = int(wrong_count / results_per_page) + (wrong_count % results_per_page > 0)

    return render_template('admin/wrong_keys.html', wrong_keys=wrong_keys, pages=pages, curr_page=page)


@admin.route('/admin/correct_keys', defaults={'page': '1'}, methods=['GET'])
@admin.route('/admin/correct_keys/<int:page>', methods=['GET'])
@admins_only
def admin_correct_key(page):
    page = abs(int(page))
    results_per_page = 50
    page_start = results_per_page * (page - 1)
    page_end = results_per_page * (page - 1) + results_per_page

    solves = Solves.query.add_columns(Solves.id, Solves.chalid, Solves.studentid, Solves.date, Solves.flag,
                                      Challenges.name.label('chal_name'), Students.name.label('student_name')) \
        .join(Challenges) \
        .join(Students) \
        .order_by(Solves.date.desc()) \
        .slice(page_start, page_end) \
        .all()

    solve_count = db.session.query(db.func.count(Solves.id)).first()[0]
    pages = int(solve_count / results_per_page) + (solve_count % results_per_page > 0)

    return render_template('admin/correct_keys.html', solves=solves, pages=pages, curr_page=page)


@admin.route('/admin/fails/all', defaults={'studentid': 'all'}, methods=['GET'])
@admin.route('/admin/fails/<int:studentid>', methods=['GET'])
@admins_only
def admin_fails(studentid):
    if studentid == "all":
        fails = WrongKeys.query.join(Students, WrongKeys.studentid == Students.id).filter(
            Students.banned == False, Students.sectionid == get_section()).count()
        solves = Solves.query.join(Students, Solves.studentid == Students.id).filter(Students.banned == False).count()
        db.session.close()
        json_data = {'fails': str(fails), 'solves': str(solves)}
        return jsonify(json_data)
    else:
        fails = WrongKeys.query.filter_by(studentid=studentid).count()
        solves = Solves.query.filter_by(studentid=studentid).count()
        db.session.close()
        json_data = {'fails': str(fails), 'solves': str(solves)}
        return jsonify(json_data)


@admin.route('/admin/chal/new', methods=['POST'])
@admins_only
def admin_create_chal():
    files = request.files.getlist('files[]')

    # TODO: Expand to support multiple flags
    flags = [{'flag': request.form['key'], 'type': int(request.form['key_type[0]'])}]
    if (request.form['prereq'] != ""):
        prereq = Challenges.query.filter(Challenges.name == request.form['prereq']).first()
        prereq = prereq.id
    else:
        prereq = None

    # Create challenge
    chal = Challenges(request.form['name'], request.form['desc'], request.form['value'], request.form['category'],
                      flags, request.form['level'], prereq)
    '''if 'hidden' in request.form:
        chal.hidden = True
    else:
        chal.hidden = False'''
    db.session.add(chal)
    db.session.commit()

    for f in files:
        upload_file(file=f, chalid=chal.id)

    db.session.commit()
    db.session.close()
    return redirect(url_for('admin.admin_chals'))


@admin.route('/admin/chal/delete', methods=['POST'])
@admins_only
def admin_delete_chal():
    challenge = Challenges.query.filter_by(id=request.form['id']).first_or_404()
    WrongKeys.query.filter_by(chalid=challenge.id).delete()
    Solves.query.filter_by(chalid=challenge.id).delete()
    Keys.query.filter_by(chal=challenge.id).delete()
    files = Files.query.filter_by(chal=challenge.id).all()
    Files.query.filter_by(chal=challenge.id).delete()
    for file in files:
        folder = os.path.dirname(os.path.join(os.path.normpath(app.root_path), 'uploads', file.location))
        rmdir(folder)
    Tags.query.filter_by(chal=challenge.id).delete()
    Challenges.query.filter_by(id=challenge.id).delete()
    db.session.commit()
    db.session.close()
    return '1'


@admin.route('/admin/chal/update', methods=['POST'])
@admins_only
def admin_update_chal():
    challenge = Challenges.query.filter_by(id=request.form['id']).first_or_404()
    challenge.name = request.form['name']
    challenge.description = request.form['desc']
    challenge.value = request.form['value']
    challenge.category = request.form['category']
    challenge.hidden = 'hidden' in request.form
    challenge.level = request.form['level']
    if (request.form['prereq'] != ""):
        prereq = Challenges.query.filter(Challenges.name == request.form['prereq']).first()
        challenge.prereq = prereq.id
    else:
        challenge.prereq = None
    db.session.add(challenge)
    db.session.commit()
    db.session.close()
    return redirect(url_for('admin.admin_chals'))


@admin.route('/admin/teams', defaults={'page': '1'})
@admin.route('/admin/teams/<int:page>')
def admin_teams(page):
    page = abs(int(page))
    results_per_page = 50
    page_start = results_per_page * (page - 1)
    page_end = results_per_page * (page - 1) + results_per_page

    stuid = session['id']
    student = Students.query.filter_by(id=stuid).first()
    count = Teams.query.filter_by(sectionNumber=student.sectionid).count()
    teams = Teams.query.filter_by(sectionNumber=student.sectionid).slice(page_start, page_end).all()

    pages = int(count / results_per_page) + (count % results_per_page > 0)
    return render_template('admin/teams.html', teams=teams, pages=pages, curr_page=page)


@admin.route('/admin/team/<int:teamid>')
def admin_team(teamid):
    if get_config('view_scoreboard_if_authed') and not authed():
        return redirect(url_for('auth.login', next=request.path))
    team = Teams.query.filter_by(id=teamid).first()
    student = Students.query.filter_by(id=session['id']).first()

    if student.sectionid != team.sectionNumber:
        return render_template('admin/wrong_section.html', section=team.sectionNumber)

    students = Students.query.filter_by(teamid=teamid)
    # get solves data by team id
    # get awards data by team id
    challenges = Challenges.query.all()
    db.session.close()
    if request.method == 'GET':
        return render_template('admin/team.html', team=team, students=students, challenges=challenges)
    elif request.method == 'POST':
        return None  # return solves data by team id

@admin.route('/admin/team/<int:teamid>/update', methods=['POST'])
def admin_update_team(teamid):
    team = Teams.query.filter(Teams.id == teamid).first()
    team.name = request.form['name']
    db.session.commit()
    db.session.close()
    return redirect('/admin/teams')


@admin.route('/admin/team/new', methods=['POST'])
def admin_create_team():
    admin = Students.query.filter_by(id=session['id']).first()
    team = Teams(request.form['name'], admin.sectionid)
    db.session.add(team)
    db.session.commit()
    db.session.close()
    return redirect(url_for('admin.admin_teams'))


@admin.route('/admin/team/<int:teamid>/challenges')
def teamChallenges(teamid):
    team = Teams.query.filter_by(id=teamid).first()
    challenges = team.challenges()
    return render_template('tChallenges.html', team=team, challenges=challenges)

@admin.route('/admin/team/<int:teamid>/challenge/<int:chalid>')
def team_challenge(teamid, chalid):
    team = Teams.query.filter_by(id=teamid).first()
    student = Students.query.filter_by(id=session['id']).first()

    if student.sectionid != team.sectionNumber:
        return render_template('admin/wrong_section.html', section=team.sectionNumber)
    # Get the challenge
    challenge = Challenges.query.filter_by(id=chalid).first()
    # Get all the students on the team and their ids
    students = Students.query.filter_by(teamid=team.id).all()
    student_ids = [s.id for s in students]
    # Get all the solves from the team for the challenge
    solves = Solves.query.filter(Solves.chalid == chalid, Solves.studentid.in_(student_ids)).all()
    solve_student_ids = [s.studentid for s in solves]
    # Get all the students who have solved and haven't solved the challenge from the team
    students_solved = Students.query.filter(Students.id.in_(solve_student_ids)).all()
    students_unsolved = Students.query.filter(not_(Students.id.in_(solve_student_ids)), Students.teamid == team.id).all()
    # Get all of the wrong submissions for the challenge from the team
    wrong_keys = WrongKeys.query.filter(WrongKeys.chalid == chalid, WrongKeys.studentid.in_(student_ids)).all()
    # Get the key for the challenge
    flags = json.loads(challenge.flags)
    key = flags[0]['flag']
    return render_template('admin/challenge.html',
                           challenge=challenge,
                           team=team,
                           students_solved=students_solved,
                           students_unsolved=students_unsolved,
                           wrong_keys=wrong_keys,
                           solves=solves,
                           key=key)


@admin.route('/admin/team/<int:teamid>/solves')
def teamSolves(teamid):
    team = Teams.query.filter_by(id=teamid).first()
    solves = team.solves()
    return render_template('tSolves.html', team=team, solves=solves)


@admin.route('/admin/new_section')
def new_section():
    return render_template('admin/new_section.html')