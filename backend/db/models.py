from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Email(db.Model):
    __tablename__ = 'emails'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    server = db.Column(db.String(100))
    port = db.Column(db.Integer)
    use_ssl = db.Column(db.Boolean, default=True)  # 添加SSL选项，默认为True
    type = db.Column(db.String(20), nullable=False)  # imap, pop3, etc.
    status = db.Column(db.String(20), default='active')  # active, disabled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Email {self.username}>' 