from flask import request, jsonify, current_app, send_from_directory, render_template, redirect, url_for, session, flash
from models import db, User, AudioFile, Team, TeamMember, TeamUpload
from extensions import bcrypt
import os
from werkzeug.utils import secure_filename
from models import Loop, Note, AudioSetting
import secrets

ALLOWED_EXTENSIONS = {'mp3'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def team_member_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        team_id = kwargs.get('team_id')
        if not team_id:
            return redirect(url_for('dashboard'))
        membership = TeamMember.query.filter_by(team_id=team_id, user_id=session['user_id']).first()
        if not membership:
            flash('You are not a member of this team.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def register_routes(app):
    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register_page():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            if not username or not email or not password:
                flash('All fields are required.', 'danger')
                return render_template('register.html')
            if User.query.filter((User.username == username) | (User.email == email)).first():
                flash('Username or email already exists.', 'danger')
                return render_template('register.html')
            pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(username=username, email=email, password_hash=pw_hash)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login_page'))
        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login_page():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and bcrypt.check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Logged out successfully.', 'info')
        return redirect(url_for('home'))

    @app.route('/teams/create', methods=['GET', 'POST'])
    @login_required
    def create_team():
        if request.method == 'POST':
            name = request.form.get('name')
            password = request.form.get('password')
            if not name or not password:
                flash('Team name and password are required.', 'danger')
                return render_template('create_team.html')
            if Team.query.filter_by(name=name).first():
                flash('Team name already exists.', 'danger')
                return render_template('create_team.html')
            pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            team = Team(name=name, password_hash=pw_hash, created_by=session['user_id'])
            db.session.add(team)
            db.session.commit()
            member = TeamMember(team_id=team.id, user_id=session['user_id'])
            db.session.add(member)
            db.session.commit()
            flash('Team created successfully!', 'success')
            return redirect(url_for('team_dashboard', team_id=team.id))
        return render_template('create_team.html')

    @app.route('/teams/join', methods=['GET', 'POST'])
    @login_required
    def join_team():
        if request.method == 'POST':
            name = request.form.get('name')
            password = request.form.get('password')
            if not name or not password:
                flash('Team name and password are required.', 'danger')
                return render_template('join_team.html')
            team = Team.query.filter_by(name=name).first()
            if not team or not bcrypt.check_password_hash(team.password_hash, password):
                flash('Invalid team name or password.', 'danger')
                return render_template('join_team.html')
            existing_member = TeamMember.query.filter_by(team_id=team.id, user_id=session['user_id']).first()
            if existing_member:
                flash('You are already a member of this team.', 'info')
                return redirect(url_for('team_dashboard', team_id=team.id))
            member = TeamMember(team_id=team.id, user_id=session['user_id'])
            db.session.add(member)
            db.session.commit()
            flash('Joined team successfully!', 'success')
            return redirect(url_for('team_dashboard', team_id=team.id))
        return render_template('join_team.html')

    @app.route('/teams/<int:team_id>')
    @team_member_required
    def team_dashboard(team_id):
        team = Team.query.get_or_404(team_id)
        uploads = TeamUpload.query.filter_by(team_id=team_id).order_by(TeamUpload.uploaded_at.desc()).all()
        folders = db.session.query(TeamUpload.folder).filter_by(team_id=team_id).distinct().all()
        folders = [folder[0] for folder in folders]
        return render_template('team_dashboard.html', team=team, uploads=uploads, folders=folders)

    @app.route('/teams/<int:team_id>/upload', methods=['GET', 'POST'])
    @team_member_required
    def team_upload(team_id):
        team = Team.query.get_or_404(team_id)
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file selected.', 'danger')
                return redirect(url_for('team_upload', team_id=team_id))
            file = request.files['file']
            folder = request.form.get('folder', 'General')
            if not file or not file.filename or not allowed_file(file.filename):
                flash('Invalid file type. Only MP3 files are allowed.', 'danger')
                return redirect(url_for('team_upload', team_id=team_id))
            filename = secure_filename(file.filename or "")
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(save_path):
                filename = f"{base}_{counter}{ext}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                counter += 1
            file.save(save_path)
            upload = TeamUpload(
                team_id=team_id,
                user_id=session['user_id'],
                filename=filename,
                original_filename=file.filename,
                folder=folder
            )
            db.session.add(upload)
            db.session.commit()
            flash('File uploaded to team successfully!', 'success')
            return redirect(url_for('team_dashboard', team_id=team_id))
        return render_template('team_upload.html', team=team)

    @app.route('/teams/<int:team_id>/download/<int:upload_id>')
    @team_member_required
    def download_team_file(team_id, upload_id):
        upload = TeamUpload.query.filter_by(id=upload_id, team_id=team_id).first_or_404()
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], upload.filename)
        if not os.path.exists(file_path):
            flash('File not found on server.', 'danger')
            return redirect(url_for('team_dashboard', team_id=team_id))
        from flask import send_file
        return send_file(
            file_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=upload.original_filename
        )

    @app.route('/teams/<int:team_id>/delete/<int:upload_id>', methods=['POST'])
    @team_member_required
    def delete_team_file(team_id, upload_id):
        upload = TeamUpload.query.filter_by(id=upload_id, team_id=team_id).first_or_404()
        if upload.user_id != session['user_id']:
            flash('You can only delete your own uploads.', 'danger')
            return redirect(url_for('team_dashboard', team_id=team_id))
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], upload.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(upload)
        db.session.commit()
        flash('File deleted successfully.', 'success')
        return redirect(url_for('team_dashboard', team_id=team_id))

    @app.route('/dashboard', methods=['GET', 'POST'])
    @login_required
    def dashboard():
        user_id = session['user_id']
        username = session['username']
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file part.', 'danger')
                return redirect(url_for('dashboard'))
            file = request.files['file']
            if not file or not file.filename or not allowed_file(file.filename):
                flash('Invalid file type.', 'danger')
                return redirect(url_for('dashboard'))
            filename = secure_filename(file.filename or "")
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(save_path):
                filename = f"{base}_{counter}{ext}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                counter += 1
            file.save(save_path)
            audio = AudioFile(user_id=user_id, filename=filename, original_filename=file.filename)
            db.session.add(audio)
            db.session.commit()
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('dashboard'))
        audio_files = AudioFile.query.filter_by(user_id=user_id).order_by(AudioFile.upload_date.desc()).all()
        user_teams = TeamMember.query.filter_by(user_id=user_id).all()
        teams = [Team.query.get(member.team_id) for member in user_teams]
        return render_template('dashboard.html', username=username, audio_files=audio_files, teams=teams)

    @app.route('/audio/<int:audio_id>', methods=['GET', 'POST'])
    @login_required
    def audio_detail(audio_id):
        user_id = session['user_id']
        audio = AudioFile.query.filter_by(id=audio_id, user_id=user_id).first_or_404()
        if request.method == 'POST':
            form_type = request.form.get('form_type')
            if form_type == 'loop':
                start_time = request.form.get('start_time', type=float)
                end_time = request.form.get('end_time', type=float)
                label = request.form.get('label', '')
                if start_time is not None and end_time is not None:
                    loop = Loop(audiofile_id=audio.id, start_time=start_time, end_time=end_time, label=label)
                    db.session.add(loop)
                    db.session.commit()
                    flash('Loop added!', 'success')
                return redirect(url_for('audio_detail', audio_id=audio.id))
            elif form_type == 'note':
                timestamp = request.form.get('timestamp', type=float)
                text = request.form.get('text', '')
                if timestamp is not None and text:
                    note = Note(audiofile_id=audio.id, timestamp=timestamp, text=text)
                    db.session.add(note)
                    db.session.commit()
                    flash('Note added!', 'success')
                return redirect(url_for('audio_detail', audio_id=audio.id))
            elif form_type == 'delete_note':
                note_id = request.form.get('note_id', type=int)
                note = Note.query.filter_by(id=note_id, audiofile_id=audio.id).first()
                if note:
                    db.session.delete(note)
                    db.session.commit()
                    flash('Note deleted!', 'success')
                return redirect(url_for('audio_detail', audio_id=audio.id))
        loops = Loop.query.filter_by(audiofile_id=audio.id).all()
        notes = Note.query.filter_by(audiofile_id=audio.id).all()
        return render_template('audio_detail.html', audio=audio, loops=loops, notes=notes)

    @app.route('/audio/<int:audio_id>/download')
    @login_required
    def download_audio(audio_id):
        user_id = session['user_id']
        audio = AudioFile.query.filter_by(id=audio_id, user_id=user_id).first_or_404()
        
        upload_folder = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
        file_path = os.path.join(upload_folder, audio.filename)
        
        print(f"Looking for file: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        print(f"Upload folder: {upload_folder}")
        print(f"Audio filename: {audio.filename}")
        print(f"Current working directory: {os.getcwd()}")
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            flash('Audio file not found on server.', 'danger')
            return redirect(url_for('dashboard'))
        
        from flask import send_file
        try:
            return send_file(
                file_path,
                mimetype='audio/mpeg',
                as_attachment=False
            )
        except Exception as e:
            print(f"Error sending file: {e}")
            flash('Error serving audio file.', 'danger')
            return redirect(url_for('dashboard'))

    @app.route('/audio/<int:audio_id>/delete', methods=['POST'])
    @login_required
    def delete_audio(audio_id):
        user_id = session['user_id']
        audio = AudioFile.query.filter_by(id=audio_id, user_id=user_id).first_or_404()
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], audio.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        Loop.query.filter_by(audiofile_id=audio.id).delete()
        Note.query.filter_by(audiofile_id=audio.id).delete()
        AudioSetting.query.filter_by(audiofile_id=audio.id).delete()
        db.session.delete(audio)
        db.session.commit()
        flash('Audio file deleted.', 'success')
        return redirect(url_for('dashboard')) 