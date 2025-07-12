from extensions import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    audio_files = db.relationship('AudioFile', backref='user', lazy=True)
    team_memberships = db.relationship('TeamMember', backref='user', lazy=True)
    team_uploads = db.relationship('TeamUpload', backref='user', lazy=True)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    members = db.relationship('TeamMember', backref='team', lazy=True)
    uploads = db.relationship('TeamUpload', backref='team', lazy=True)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class TeamUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    folder = db.Column(db.String(100), default='General')
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class AudioFile(db.Model):
    __tablename__ = 'audiofile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    loops = db.relationship('Loop', backref='audiofile', lazy=True)
    notes = db.relationship('Note', backref='audiofile', lazy=True)
    settings = db.relationship('AudioSetting', backref='audiofile', lazy=True, uselist=False)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class Loop(db.Model):
    __tablename__ = 'loop'
    id = db.Column(db.Integer, primary_key=True)
    audiofile_id = db.Column(db.Integer, db.ForeignKey('audiofile.id'), nullable=False)
    start_time = db.Column(db.Float, nullable=False)
    end_time = db.Column(db.Float, nullable=False)
    label = db.Column(db.String(128))
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class Note(db.Model):
    __tablename__ = 'note'
    id = db.Column(db.Integer, primary_key=True)
    audiofile_id = db.Column(db.Integer, db.ForeignKey('audiofile.id'), nullable=False)
    timestamp = db.Column(db.Float, nullable=False)
    text = db.Column(db.String(512))
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class AudioSetting(db.Model):
    __tablename__ = 'audiosetting'
    id = db.Column(db.Integer, primary_key=True)
    audiofile_id = db.Column(db.Integer, db.ForeignKey('audiofile.id'), nullable=False)
    speed = db.Column(db.Float, default=1.0)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)