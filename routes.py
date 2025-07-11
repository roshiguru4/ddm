from flask import request, jsonify, current_app, send_from_directory, render_template, redirect, url_for, session, flash
from models import db, User, AudioFile
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
        return render_template('dashboard.html', username=username, audio_files=audio_files)

    @app.route('/audio/<int:audio_id>', methods=['GET', 'POST'])
    @login_required
    def audio_detail(audio_id):
        user_id = session['user_id']
        audio = AudioFile.query.filter_by(id=audio_id, user_id=user_id).first_or_404()
        if request.method == 'POST' and 'start_time' in request.form:
            start_time = request.form.get('start_time', type=float)
            end_time = request.form.get('end_time', type=float)
            label = request.form.get('label', '')
            if start_time is not None and end_time is not None:
                loop = Loop(audiofile_id=audio.id, start_time=start_time, end_time=end_time, label=label)
                db.session.add(loop)
                db.session.commit()
                flash('Loop added!', 'success')
            return redirect(url_for('audio_detail', audio_id=audio.id))
        if request.method == 'POST' and 'timestamp' in request.form:
            timestamp = request.form.get('timestamp', type=float)
            text = request.form.get('text', '')
            if timestamp is not None and text:
                note = Note(audiofile_id=audio.id, timestamp=timestamp, text=text)
                db.session.add(note)
                db.session.commit()
                flash('Note added!', 'success')
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