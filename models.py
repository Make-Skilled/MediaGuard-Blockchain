from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    profile_pic = db.Column(db.String(64), default='default.jpg')
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Blockchain-related fields
    wallet_address = db.Column(db.String(42), unique=True)
    is_registered_on_blockchain = db.Column(db.Boolean, default=False)
    violation_count = db.Column(db.Integer, default=0)
    is_blocked = db.Column(db.Boolean, default=False)
    blocked_at = db.Column(db.DateTime)
    unblock_request = db.Column(db.Boolean, default=False)
    unblock_request_date = db.Column(db.DateTime)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)
    followers = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy=True)
    following = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def increment_violations(self):
        self.violation_count += 1
        if self.violation_count >= 3:
            self.is_blocked = True
            self.blocked_at = datetime.utcnow()
    
    def request_unblock(self):
        if self.is_blocked and not self.unblock_request:
            self.unblock_request = True
            self.unblock_request_date = datetime.utcnow()
            return True
        return False
    
    def unblock(self):
        if self.is_blocked:
            self.is_blocked = False
            self.violation_count = 0
            self.unblock_request = False
            self.unblock_request_date = None
            return True
        return False

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500))
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)
    
    # Blockchain-related fields
    blockchain_post_id = db.Column(db.Integer)
    content_hash = db.Column(db.String(66))
    vulgarity_score = db.Column(db.Float)
    is_blocked_on_blockchain = db.Column(db.Boolean, default=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 