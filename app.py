# --- 1. Import all necessary libraries ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from datetime import datetime # For timestamps
import requests # For API calls
from flask_sqlalchemy import SQLAlchemy # For the database
from flask_login import (
    LoginManager, 
    UserMixin, 
    login_user, 
    login_required, 
    logout_user, 
    current_user
) # For user login
from flask_bcrypt import Bcrypt # For password encryption
import os # (This is needed to create folders)

# --- 2. Flask App Configuration ---
app = Flask(__name__)
# Will create database.db next to app.py
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' 
app.config['SECRET_KEY'] = 'any_secret_key_will_do' # For securing the session

# --- 3. Initialize Extensions ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # If not logged in, redirect to /login
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "flash-message" # (To match our CSS)

# --- 4. Database Models ---

# 4a. Table for Users
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(50), nullable=True, default='Jabalpur') 
    # Connects User and Post (will be used by 'author')
    posts = db.relationship('Post', backref='author', lazy=True)

# 4b. Table for Questions/Posts
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # This creates a relationship with the 'User' table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- 5. Flask-Login User Loader ---
# This function tells Flask-Login how to load a user from the session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 6. Main Page Routes ---

# 6a. Home Page (http://127.0.0.1:5000)
@app.route('/')
def index():
    return render_template('index.html') # This will show 'index.html' (Weather/Market)

# 6b. Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard')) # If already logged in, send to Dashboard
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user) # Logs the user in
            flash('Login Successful!', 'flash-message-success') # (Success message)
            return redirect(url_for('dashboard')) # Send to Dashboard
        else:
            flash('Incorrect username or password.') # (This will be red by default)

    return render_template('login.html') # This will only show 'login.html' on /login

# 6c. Register Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard')) # If already logged in, send to Dashboard

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Create the user with a default city (Jabalpur)
        new_user = User(username=username, password=hashed_password, city='Jabalpur')
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('Account created! You can now log in.', 'flash-message-success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('That username is already taken.')
            print(f"Register Error: {e}")
            return redirect(url_for('register'))
            
    return render_template('register.html')

# 6d. Logout
@app.route('/logout')
@login_required 
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 7. Protected Page Routes ---

# 7a. Dashboard
@app.route('/dashboard')
@login_required # (This is required here)
def dashboard():
    return render_template('dashboard.html')

# 7b. Update City
@app.route('/update_city', methods=['POST'])
@login_required
def update_city():
    new_city = request.form['city']
    current_user.city = new_city
    db.session.commit()
    flash('Your city has been updated!', 'flash-message-success')
    return redirect(url_for('dashboard'))

# 7c. Schemes Page
@app.route('/schemes')
def schemes():
    return render_template('schemes.html')

# 7d. Community Q&A Page
@app.route('/community')
@login_required
def community():
    all_posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('community.html', posts=all_posts)

# 7e. Ask a Post
@app.route('/ask_post', methods=['POST'])
@login_required
def ask_post():
    post_content = request.form['post_content']
    new_post = Post(content=post_content, author=current_user)
    db.session.add(new_post)
    db.session.commit()
    flash('Your post has been submitted!', 'flash-message-success')
    return redirect(url_for('community'))

# --- 8. AI Helper (Gemini) Routes (New) ---

# 8a. Function to call the AI
def run_gemini(user_question):
    # !!! IMPORTANT: Get your NEW, SAFE API Key from Google AI Studio !!!
    API_KEY = "YAHAN_APNI_KEY_DALEN" # <-- PASTE YOUR NEW KEY HERE
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={API_KEY}"
    
    system_prompt = (
        "You are 'Krishi Mitra', an AI assistant for Indian farmers."
        "You must provide all answers in English."
        "Your answers should be short, easy to understand, and focused on Indian agriculture (crops, weather, government schemes, soil)."
    )
    
    payload = {
        "contents": [{"parts": [{"text": user_question}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }
    
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status() 
        result = response.json()
        text_response = result['candidates'][0]['content']['parts'][0]['text']
        html_response = text_response.replace('\n', '<br>')
        return html_response
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return ("Sorry, the AI assistant is currently unavailable. Please try again later. "
                "Error: " + str(e))

# 8b. Route to display the AI page
@app.route('/ai_helper', methods=['GET', 'POST'])
@login_required
def ai_helper():
    answer = None
    if request.method == 'POST':
        user_question = request.form['user_question']
        answer = run_gemini(user_question)
    return render_template('ai_helper.html', answer=answer)

# --- 9. Background API Routes (for JavaScript) ---

# 9a. Weather API
@app.route('/api/weather')
def get_weather():
    if current_user.is_authenticated:
        city = current_user.city # User's saved city
    else:
        city = "Jabalpur" # Default city (if not logged in)

    # !!! IMPORTANT: This is your Weather API Key !!!
    WEATHER_API_KEY = "YAHAN_APNI_KEY_DALEN" # <-- PASTE YOUR NEW KEY HERE
    try:
        # --- HTTPS FIX IS HERE ---
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        full_url = f"{base_url}?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=en" # Changed lang to 'en'
        response = requests.get(full_url)
        data = response.json() 

        weather_data = {
            "temperature": f"{data['main']['temp']}°C",
            "condition": data['weather'][0]['description'].capitalize(),
            "humidity": f"{data['main']['humidity']}%"
        }
        return jsonify(weather_data)
    except Exception as e:
        print(f"Weather API Error: {e}")
        # If user's city is wrong, show default
        city = "Jabalpur"
        # --- HTTPS FIX IS HERE ---
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        full_url = f"{base_url}?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=en" # Changed lang to 'en'
        response = requests.get(full_url)
        data = response.json()
        weather_data = {
            "temperature": f"{data['main']['temp']}°C",
            "condition": data['weather'][0]['description'].capitalize(),
            "humidity": f"{data['main']['humidity']}%"
        }
        return jsonify(weather_data)

# 9b. Market Prices API
@app.route('/api/market_prices')
def get_market_prices():
    # (Placeholder data for now - now in English)
    prices = [
        {"crop": "Wheat", "price": "₹2250 / Quintal"},
        {"crop": "Tomato", "price": "₹1800 / Quintal"},
        {"crop": "Potato", "price": "₹2100 / Quintal"}
    ]
    return jsonify(prices)

# --- 10. Run the App (Simpler) ---
if __name__ == '__main__':
    # Before starting the server, create the database tables (next to app.py)
    with app.app_context():
        db.create_all()
        print("Database tables checked/created next to app.py.")

    # Now, run the app
    app.run(debug=True)

