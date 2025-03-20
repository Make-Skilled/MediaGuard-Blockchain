# Social Media Application

A feature-rich social media platform built with Flask that allows users to share photos and videos, follow other users, and interact through likes and comments.

## Features

### User Management
- User registration and authentication
- Profile customization with profile pictures and bio
- Follow/unfollow system
- View followers and following lists

### Posts
- Create posts with images or videos
- Add captions to posts
- Like and comment on posts
- View posts in a grid layout on profiles
- Detailed post view with comments

### Search
- Search for users by username or bio
- Case-insensitive partial matching
- Follow users directly from search results

### Feed
- Personalized feed showing posts from followed users
- View all posts when not following anyone
- Interactive post engagement

## Technical Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy
- **Frontend**: 
  - HTML/CSS
  - Tailwind CSS for styling
  - JavaScript for interactivity
- **Authentication**: Flask-Login
- **File Handling**: Support for image and video uploads

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Initialize the database:
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```
5. Run the application:
   ```bash
   flask run
   ```

## Usage

1. Register a new account or login with existing credentials
2. Customize your profile with a picture and bio
3. Create posts by uploading images or videos
4. Follow other users to see their posts in your feed
5. Interact with posts through likes and comments
6. Search for other users using the search bar
7. View your profile to see all your posts in a grid layout

## Directory Structure

```
.
├── app.py              # Main application file
├── static/            
│   ├── css/           # CSS files
│   ├── js/            # JavaScript files
│   └── img/           # Uploaded images and videos
├── templates/          # HTML templates
│   ├── base.html      # Base template
│   ├── profile.html   # User profile page
│   ├── feed.html      # Home feed
│   └── ...            # Other templates
└── requirements.txt    # Python dependencies
```

## Security Features

- Password hashing
- CSRF protection
- Secure file uploads
- User session management
- Protected routes

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License. 