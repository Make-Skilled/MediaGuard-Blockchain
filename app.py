from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from PIL import Image
from slugify import slugify
from transformers import CLIPProcessor, CLIPModel
import torch
import cv2
import numpy as np
from moviepy.editor import VideoFileClip
from flask_wtf import FlaskForm
from wtforms import StringField, FileField, TextAreaField
from wtforms.validators import DataRequired, Length
from markupsafe import Markup
from werkzeug.utils import secure_filename
from functools import wraps
from content_analyzer import analyze_content
from blockchain import blockchain
import hashlib
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mediaGuard.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/img/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize CLIP model for content moderation
try:
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()
except Exception as e:
    print(f"Error loading CLIP model: {e}")
    model = None
    processor = None

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class Follows(db.Model):
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    profile_pic = db.Column(db.String(120), default='default.jpg')
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('Post', backref='author', lazy=True)
    violation_count = db.Column(db.Integer, default=0)
    is_blocked = db.Column(db.Boolean, default=False)
    blocked_at = db.Column(db.DateTime)
    unblock_request = db.Column(db.Boolean, default=False)
    unblock_request_date = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    wallet_address = db.Column(db.String(42), unique=True, nullable=True)
    is_registered_on_blockchain = db.Column(db.Boolean, default=False)
    
    # Add following relationship
    following = db.relationship(
        'User',
        secondary='follows',
        primaryjoin=(id == Follows.follower_id),
        secondaryjoin=(id == Follows.followed_id),
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.is_admin and not self.wallet_address:
            raise ValueError("Non-admin users must have a wallet address")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def increment_violation(self):
        self.violation_count += 1
        if self.violation_count >= 3:  # Block after 3 violations
            self.is_blocked = True
            self.blocked_at = datetime.utcnow()
        db.session.commit()

    def request_unblock(self):
        self.unblock_request = True
        self.unblock_request_date = datetime.utcnow()
        db.session.commit()

    def unblock(self):
        self.is_blocked = False
        self.violation_count = 0
        self.unblock_request = False
        self.unblock_request_date = None
        db.session.commit()

class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    is_like = db.Column(db.Boolean, nullable=False)  # True for like, False for dislike
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    is_like = db.Column(db.Boolean, nullable=False)  # True for like, False for dislike
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('PostLike', backref='post', lazy=True)
    dislikes = db.relationship('PostLike', backref='post_disliked', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    is_video = db.Column(db.Boolean, default=False)
    vulgarity_score = db.Column(db.Float, default=0.0)
    content_category = db.Column(db.String(20), default='safe')
    content_hash = db.Column(db.String(64))
    blockchain_post_id = db.Column(db.Integer)

    def get_likes_count(self):
        return PostLike.query.filter_by(post_id=self.id, is_like=True).count()

    def get_dislikes_count(self):
        return PostLike.query.filter_by(post_id=self.id, is_like=False).count()

    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return PostLike.query.filter_by(post_id=self.id, user_id=user.id, is_like=True).first() is not None

    def is_disliked_by(self, user):
        if not user.is_authenticated:
            return False
        return PostLike.query.filter_by(post_id=self.id, user_id=user.id, is_like=False).first() is not None

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    likes = db.relationship('CommentLike', backref='comment', lazy=True)
    dislikes = db.relationship('CommentLike', backref='comment_disliked', lazy=True)

    def get_likes_count(self):
        return CommentLike.query.filter_by(comment_id=self.id, is_like=True).count()

    def get_dislikes_count(self):
        return CommentLike.query.filter_by(comment_id=self.id, is_like=False).count()

    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return CommentLike.query.filter_by(comment_id=self.id, user_id=user.id, is_like=True).first() is not None

    def is_disliked_by(self, user):
        if not user.is_authenticated:
            return False
        return CommentLike.query.filter_by(comment_id=self.id, user_id=user.id, is_like=False).first() is not None

class PostForm(FlaskForm):
    image = FileField('Image', validators=[DataRequired()])
    caption = TextAreaField('Caption', validators=[Length(max=500)])

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    profile_pic = FileField('Profile Picture')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(max=500)])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        # Get posts from users that the current user follows
        followed_users = [user.id for user in current_user.following]
        followed_users.append(current_user.id)
        posts = Post.query.filter(Post.user_id.in_(followed_users)).order_by(Post.created_at.desc()).all()
        
        # If no posts from followed users, get all posts
        if not posts:
            posts = Post.query.order_by(Post.created_at.desc()).all()
    else:
        # For non-logged in users, show all posts
        posts = Post.query.order_by(Post.created_at.desc()).all()
    
    post_form = PostForm()
    comment_form = CommentForm()
    return render_template('index.html', posts=posts, form=comment_form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        wallet_address = request.form.get('wallet_address')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(wallet_address=wallet_address).first():
            flash('Wallet address already registered', 'error')
            return redirect(url_for('register'))
        
        # Validate wallet address format
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            flash('Invalid wallet address format. Please enter a valid Ethereum address.', 'error')
            return redirect(url_for('register'))
        
        try:
            # Create user in database
            user = User(username=username, email=email, wallet_address=wallet_address)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            # Register user on blockchain
            try:
                if blockchain.register_user(wallet_address):
                    user.is_registered_on_blockchain = True
                    db.session.commit()
                    flash('Registration successful! Please login.', 'success')
                else:
                    # If blockchain registration fails, we'll still keep the user but mark them as not registered on blockchain
                    flash('Registration successful but blockchain registration failed. You can still use the platform, but some features may be limited.', 'warning')
            except Exception as e:
                print(f"Blockchain registration error: {str(e)}")
                flash('Registration successful but blockchain registration failed. You can still use the platform, but some features may be limited.', 'warning')
            
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template('profile.html', user=user, posts=posts)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    
    if form.validate_on_submit():
        # Update username if changed
        if form.username.data != current_user.username:
            # Check if username is already taken
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already taken')
                return redirect(url_for('edit_profile'))
            current_user.username = form.username.data
        
        # Update bio
        current_user.bio = form.bio.data
        
        # Handle profile picture upload
        if form.profile_pic.data:
            file = form.profile_pic.data
            if file.filename:
                # Generate unique filename
                filename = f"profile-{slugify(current_user.username)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Process and save image
                img = Image.open(file)
                img = img.convert('RGB')
                img.thumbnail((200, 200))  # Profile picture size
                img.save(filepath, 'JPEG', quality=85)
                
                # Delete old profile picture if it exists and is not the default
                if current_user.profile_pic != 'default.jpg':
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_pic)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                
                current_user.profile_pic = filename
        
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('profile', username=current_user.username))
    
    # Pre-fill form with current user data
    form.username.data = current_user.username
    form.bio.data = current_user.bio
    
    return render_template('edit_profile.html', form=form)

def calculate_vulgarity_score(image_features, text_features, inappropriate_features, safe_features):
    """Calculate a numerical vulgarity score between 0.0 and 1.0."""
    # Calculate similarity scores
    inappropriate_scores = torch.cosine_similarity(image_features, inappropriate_features)
    safe_scores = torch.cosine_similarity(image_features, safe_features)
    
    # Get maximum scores
    max_inappropriate = torch.max(inappropriate_scores).item()
    max_safe = torch.max(safe_scores).item()
    
    # Calculate score (0.0 to 1.0)
    total = max_inappropriate + max_safe
    if total == 0:
        return 0.0
    score = max_inappropriate / total
    
    return score

def get_content_category(score):
    """Convert vulgarity score to content category."""
    if score < 0.2:
        return "safe"
    elif score < 0.4:
        return "mild"
    elif score < 0.7:
        return "moderate"
    else:
        return "explicit"

def analyze_content(image, caption):
    """Analyze both image and caption for inappropriate content."""
    if not model or not processor:
        return True, 0.0, "safe"  # Allow content if model is not available
    
    # Define inappropriate content categories
    inappropriate_categories = [
        "adult content", "explicit content", "nsfw", "inappropriate content",
        "vulgar content", "offensive content", "hate speech", "violence",
        "graphic content", "disturbing content", "sexual content",
        "drugs and alcohol", "gore", "extreme violence"
    ]
    
    # Define safe content categories
    safe_categories = [
        "family friendly", "safe content", "appropriate content",
        "wholesome content", "general audience", "suitable for all",
        "educational content", "artistic content", "nature content",
        "food and cooking", "travel and adventure"
    ]
    
    try:
        # Process image
        image_inputs = processor(images=image, return_tensors="pt")
        image_features = model.get_image_features(**image_inputs)
        
        # Process text (caption)
        text_inputs = processor(text=caption, return_tensors="pt", padding=True, truncation=True)
        text_features = model.get_text_features(**text_inputs)
        
        # Compare with inappropriate categories
        inappropriate_texts = processor(text=inappropriate_categories, return_tensors="pt", padding=True, truncation=True)
        inappropriate_features = model.get_text_features(**inappropriate_texts)
        
        # Compare with safe categories
        safe_texts = processor(text=safe_categories, return_tensors="pt", padding=True, truncation=True)
        safe_features = model.get_text_features(**safe_texts)
        
        # Calculate vulgarity score
        score = calculate_vulgarity_score(image_features, text_features, inappropriate_features, safe_features)
        category = get_content_category(score)
        
        # Allow content if score is below threshold
        return score < 0.7, score, category
        
    except Exception as e:
        print(f"Error in content analysis: {e}")
        return True, 0.0, "safe"  # Allow content if analysis fails

def extract_video_frames(video_path, max_frames=10):
    """Extract frames from video for analysis."""
    frames = []
    try:
        video = cv2.VideoCapture(video_path)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        
        # Calculate frame interval
        interval = total_frames // max_frames
        
        for i in range(max_frames):
            video.set(cv2.CAP_PROP_POS_FRAMES, i * interval)
            ret, frame = video.read()
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(frame_rgb))
        
        video.release()
    except Exception as e:
        print(f"Error extracting video frames: {e}")
    
    return frames

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.is_blocked:
        flash('Your account has been blocked due to multiple content violations. Please request an unblock from the admin.', 'error')
        return redirect(url_for('profile', username=current_user.username))

    form = PostForm()
    if form.validate_on_submit():
        if form.image.data:
            filename = secure_filename(form.image.data.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            form.image.data.save(file_path)
            
            # Check if it's a video
            is_video = filename.lower().endswith(('.mp4', '.avi', '.mov', '.wmv'))
            
            try:
                if is_video:
                    # Extract frames from video for analysis
                    frames = extract_video_frames(file_path)
                    if not frames:
                        flash('Error processing video file')
                        os.remove(file_path)
                        return redirect(url_for('create_post'))
                    
                    # Analyze each frame
                    max_score = 0.0
                    max_category = "safe"
                    for frame in frames:
                        is_safe, score, category = analyze_content(frame, form.caption.data)
                        max_score = max(max_score, score)
                        if score > max_score:
                            max_category = category
                    
                    # Clean up frames
                    for frame in frames:
                        frame.close()
                    
                    is_safe = max_score < 0.7
                    vulgarity_score = max_score
                    content_category = max_category
                else:
                    # Load and process image
                    img = Image.open(file_path)
                    img = img.convert('RGB')
                    img.thumbnail((1080, 1080))  # Instagram-like size
                    img.save(file_path, 'JPEG', quality=85)
                    
                    # Analyze content
                    is_safe, vulgarity_score, content_category = analyze_content(img, form.caption.data)
                
                if not is_safe or vulgarity_score > 0.5:  # If content is unsafe or vulgarity score is above 50%
                    # Delete the uploaded file
                    os.remove(file_path)
                    # Increment user's violation count
                    current_user.increment_violation()
                    
                    if current_user.is_blocked:
                        flash('Your account has been blocked due to multiple content violations. Please request an unblock from the admin.', 'error')
                    else:
                        flash(f'Warning: Your post contains inappropriate content (Vulgarity Score: {vulgarity_score:.1%}). This is violation #{current_user.violation_count}. Your account will be blocked after 3 violations.', 'warning')
                    return redirect(url_for('create_post'))
                
                # Calculate content hash
                with open(file_path, 'rb') as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()
                
                # Create post on blockchain
                if blockchain.create_post(current_user.wallet_address, content_hash, int(vulgarity_score * 100)):
                    post = Post(
                        image=filename,
                        caption=form.caption.data,
                        user_id=current_user.id,
                        is_video=is_video,
                        vulgarity_score=vulgarity_score,
                        content_category=content_category,
                        content_hash=content_hash,
                        blockchain_post_id=blockchain.media_guard_contract.functions.getPostCount().call() - 1
                    )
                    db.session.add(post)
                    db.session.commit()
                    flash('Post created successfully!', 'success')
                else:
                    flash('Post created but blockchain registration failed. Please contact support.', 'warning')
                return redirect(url_for('index'))
                
            except Exception as e:
                print(f"Error processing file: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                flash('Error processing your file. Please try again.')
                return redirect(url_for('create_post'))
                
    return render_template('create_post.html', form=form)

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = PostLike.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    
    if existing_like:
        if existing_like.is_like:
            db.session.delete(existing_like)
        else:
            existing_like.is_like = True
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id, is_like=True)
        db.session.add(new_like)
    
    db.session.commit()
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/post/<int:post_id>/dislike', methods=['POST'])
@login_required
def dislike_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = PostLike.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    
    if existing_like:
        if not existing_like.is_like:
            db.session.delete(existing_like)
        else:
            existing_like.is_like = False
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id, is_like=False)
        db.session.add(new_like)
    
    db.session.commit()
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    return render_template('post_detail.html', post=post, form=form)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    if form.validate_on_submit():
        comment = Comment(
            content=form.content.data,
            user_id=current_user.id,
            post_id=post.id
        )
        db.session.add(comment)
        db.session.commit()
        flash('Comment added successfully')
    
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    if comment.user_id != current_user.id:
        flash('You cannot delete this comment')
        return redirect(url_for('post_detail', post_id=comment.post_id))
    
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted successfully')
    
    return redirect(url_for('post_detail', post_id=comment.post_id))

@app.route('/comment/<int:comment_id>/like', methods=['POST'])
@login_required
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=current_user.id).first()
    
    if existing_like:
        if existing_like.is_like:
            db.session.delete(existing_like)
        else:
            existing_like.is_like = True
    else:
        new_like = CommentLike(user_id=current_user.id, comment_id=comment_id, is_like=True)
        db.session.add(new_like)
    
    db.session.commit()
    return redirect(url_for('post_detail', post_id=comment.post_id))

@app.route('/comment/<int:comment_id>/dislike', methods=['POST'])
@login_required
def dislike_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=current_user.id).first()
    
    if existing_like:
        if not existing_like.is_like:
            db.session.delete(existing_like)
        else:
            existing_like.is_like = False
    else:
        new_like = CommentLike(user_id=current_user.id, comment_id=comment_id, is_like=False)
        db.session.add(new_like)
    
    db.session.commit()
    return redirect(url_for('post_detail', post_id=comment.post_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin privileges to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/blocked_users')
@login_required
@admin_required
def blocked_users():
    blocked_users = User.query.filter_by(is_blocked=True).order_by(User.blocked_at.desc()).all()
    return render_template('admin/blocked_users.html', blocked_users=blocked_users)

@app.route('/admin/analyze_user/<int:user_id>')
@login_required
@admin_required
def analyze_user(user_id):
    user = User.query.get_or_404(user_id)
    high_vulgarity_posts = Post.query.filter_by(user_id=user_id).filter(Post.vulgarity_score > 0.5).all()
    
    # Delete high vulgarity posts
    for post in high_vulgarity_posts:
        # Delete the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(post)
    
    # Unblock user
    user.unblock()
    db.session.commit()
    
    flash(f'User {user.username} has been unblocked and {len(high_vulgarity_posts)} inappropriate posts have been removed.', 'success')
    return redirect(url_for('blocked_users'))

@app.route('/request_unblock', methods=['POST'])
@login_required
def request_unblock():
    if current_user.is_blocked:
        if blockchain.request_unblock(current_user.wallet_address):
            if current_user.request_unblock():
                db.session.commit()
                flash('Unblock request submitted successfully', 'success')
            else:
                flash('You already have a pending unblock request', 'warning')
        else:
            flash('Failed to submit unblock request on blockchain', 'error')
    else:
        flash('Your account is not blocked', 'info')
    return redirect(url_for('profile', username=current_user.username))

@app.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    # Check if any admin exists
    if User.query.filter_by(is_admin=True).first():
        flash('Admin user already exists.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('setup_admin'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('setup_admin'))
        
        # Create admin user
        admin = User(username=username, email=email, is_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        
        flash('Admin user created successfully. Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('setup_admin.html')

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Get statistics
    stats = {
        'total_users': User.query.count(),
        'total_posts': Post.query.count(),
        'blocked_users': User.query.filter_by(is_blocked=True).count(),
        'unblock_requests': User.query.filter_by(unblock_request=True).count(),
        'total_violations': db.session.query(db.func.sum(User.violation_count)).scalar() or 0,
        'recent_posts': Post.query.order_by(Post.created_at.desc()).limit(5).all(),
        'recent_blocked': User.query.filter_by(is_blocked=True).order_by(User.blocked_at.desc()).limit(5).all(),
        'recent_unblock_requests': User.query.filter_by(unblock_request=True).order_by(User.unblock_request_date.desc()).limit(5).all(),
        'content_categories': db.session.query(Post.content_category, db.func.count(Post.id)).group_by(Post.content_category).all()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    if user == current_user:
        flash('You cannot follow yourself.', 'error')
        return redirect(url_for('profile', username=username))
    
    if user in current_user.following:
        flash('You are already following this user.', 'error')
        return redirect(url_for('profile', username=username))
    
    current_user.following.append(user)
    db.session.commit()
    flash(f'You are now following {username}.', 'success')
    return redirect(url_for('profile', username=username))

@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    if user == current_user:
        flash('You cannot unfollow yourself.', 'error')
        return redirect(url_for('profile', username=username))
    
    if user not in current_user.following:
        flash('You are not following this user.', 'error')
        return redirect(url_for('profile', username=username))
    
    current_user.following.remove(user)
    db.session.commit()
    flash(f'You have unfollowed {username}.', 'success')
    return redirect(url_for('profile', username=username))

@app.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers = user.followers.all()
    return render_template('followers.html', user=user, followers=followers)

@app.route('/following/<username>')
def following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following = user.following.all()
    return render_template('following.html', user=user, following=following)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        # Search for users by username or bio
        users = User.query.filter(
            (User.username.ilike(f'%{query}%')) |
            (User.bio.ilike(f'%{query}%'))
        ).all()
    else:
        users = []
    
    return render_template('search.html', users=users, query=query)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 