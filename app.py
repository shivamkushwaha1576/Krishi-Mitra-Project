import os
import io
import base64
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

# --- 1. कॉन्फ़िगरेशन और सेटअप ---

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# API Keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')

app.config['GOOGLE_API_KEY'] = GOOGLE_API_KEY
app.config['OPENWEATHER_API_KEY'] = OPENWEATHER_API_KEY

# Gemini AI सेटअप
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# डेटाबेस कॉन्फ़िगरेशन
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- 2. डेटाबेस मॉडल ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='farmer')
    shop_name = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    inventory_items = db.relationship('InventoryItem', backref='owner', lazy=True)
    soil_samples = db.relationship('SoilSample', backref='farmer_owner', lazy=True)

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(100), nullable=False)
    price = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SoilSample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending')


# --- 3. यूज़र ऑथेंटिकेशन ---

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        if User.query.filter_by(email=email).first():
            flash('यह ईमेल पहले से रजिस्टर है।', 'warning')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(fullname=fullname, email=email, password=hashed_password, role='farmer', phone=phone, address=address)
        db.session.add(new_user)
        db.session.commit()
        flash('रजिस्ट्रेशन सफल! कृपया लॉगिन करें।', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/register-shop', methods=['GET', 'POST'])
def register_shop():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        shop_name = request.form.get('shop_name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        address = request.form.get('address')

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(fullname=fullname, email=email, password=hashed_password, role='shop', shop_name=shop_name, phone=phone, address=address)
        db.session.add(new_user)
        db.session.commit()
        flash('शॉप रजिस्ट्रेशन सफल!', 'success')
        return redirect(url_for('login'))
    return render_template('register_shop.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('लॉगिन सफल!', 'success')
            return redirect(url_for('shop_dashboard') if user.role == 'shop' else url_for('dashboard'))
        else:
            flash('लॉगिन फेल। ईमेल या पासवर्ड चेक करें।', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# --- 4. मुख्य फीचर्स ---

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'farmer': return redirect(url_for('home'))
    my_rentals = InventoryItem.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', my_rentals=my_rentals)

@app.route('/shop-dashboard')
@login_required
def shop_dashboard():
    if current_user.role != 'shop': return redirect(url_for('home'))
    inventory = InventoryItem.query.filter_by(user_id=current_user.id).all()
    return render_template('shop_dashboard.html', inventory=inventory)

@app.route('/add-inventory', methods=['POST'])
@login_required
def add_inventory():
    item_name = request.form.get('item_name')
    quantity = request.form.get('quantity')
    price = request.form.get('price')
    if item_name:
        new_item = InventoryItem(item_name=item_name, quantity=quantity, price=price, user_id=current_user.id)
        db.session.add(new_item)
        db.session.commit()
        flash('आइटम जोड़ा गया!', 'success')
    return redirect(url_for('shop_dashboard') if current_user.role == 'shop' else url_for('dashboard'))

@app.route('/delete-inventory/<int:item_id>', methods=['POST'])
@login_required
def delete_inventory(item_id):
    item = db.session.get(InventoryItem, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('आइटम हटाया गया।', 'success')
    return redirect(url_for('shop_dashboard') if current_user.role == 'shop' else url_for('dashboard'))

@app.route('/tool-search', methods=['GET', 'POST'])
def tool_search():
    results = []
    search_term = ""
    location_term = ""
    if request.method == 'POST':
        search_term = request.form.get('search_query')
        location_term = request.form.get('location')
        query = InventoryItem.query
        if search_term: query = query.filter(InventoryItem.item_name.ilike(f"%{search_term}%"))
        if location_term: query = query.join(User).filter(User.address.ilike(f"%{location_term}%"))
        results = query.all()
    return render_template('tool_search.html', results=results)


# --- 5. AI फीचर्स (SMART FIX) ---

# 🛠️ हेल्पर फंक्शन: यह अपने आप सबसे अच्छा काम करने वाला मॉडल ढूँढ लेगा
def get_best_model():
    try:
        # उपलब्ध मॉडल्स की लिस्ट निकालें
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # हमारी पसंद (Priority List)
        priority_list = [
            'models/gemini-1.5-flash',
            'gemini-1.5-flash',
            'models/gemini-1.5-flash-001',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-pro'
        ]
        
        # प्राथमिकता सूची में से चेक करें
        for p in priority_list:
            if p in all_models:
                print(f"✅ Selected Model: {p}")
                return p
        
        # अगर कोई न मिले, तो कोई भी 'flash' वाला
        for m in all_models:
            if 'flash' in m.lower():
                print(f"✅ Selected Fallback Model: {m}")
                return m
                
        # अंतिम विकल्प
        if all_models:
            return all_models[0]
            
    except Exception as e:
        print(f"Warning in model selection: {e}")
    
    return 'models/gemini-1.5-flash' # Default safe bet


# A. फसल ग्रेडिंग
@app.route('/crop-grading', methods=['GET', 'POST'])
def crop_grading():
    result = None
    if request.method == 'POST':
        if 'file' not in request.files: return render_template('crop_grading.html', result="No file")
        file = request.files['file']
        if file.filename == '': return render_template('crop_grading.html', result="No selected file")
        
        if file:
            try:
                image_data = file.read()
                image_parts = [{"mime_type": file.content_type, "data": image_data}]
                
                prompt = """
                फसल विश्लेषण रिपोर्ट (हिंदी में HTML):
                1. <h3>गुणवत्ता ग्रेड:</h3> (A/B/C)
                2. <h3>स्थिति:</h3> ताज़गी और बीमारी
                3. <h3>शेल्फ लाइफ:</h3> कितने दिन चलेगा?
                4. <h3>कीमत टिप:</h3> व्यापारी से क्या बोलें?
                """
                
                # स्मार्ट मॉडल सेलेक्शन
                selected_model = get_best_model()
                model = genai.GenerativeModel(selected_model)
                response = model.generate_content([prompt, image_parts[0]])
                result = response.text

            except Exception as e:
                if "429" in str(e):
                    result = f"<p style='color:red'><b>कोटा पूरा हो गया:</b> कृपया 1 मिनट इंतज़ार करें।</p>"
                else:
                    result = f"<p style='color:red'>AI Error: {str(e)}</p>"

    return render_template('crop_grading.html', result=result)

# B. रोग पहचान
@app.route('/plant-disease', methods=['GET', 'POST'])
@login_required
def plant_disease():
    diagnosis_result = None
    uploaded_image_b64 = None
    if request.method == 'POST':
        file = request.files.get('leaf-image')
        if file and file.filename:
            try:
                img_bytes = file.read()
                uploaded_image_b64 = base64.b64encode(img_bytes).decode('utf-8')
                
                # स्मार्ट मॉडल सेलेक्शन
                selected_model = get_best_model()
                model = genai.GenerativeModel(selected_model)
                
                prompt = "यह पौधे की पत्ती है। बीमारी और इलाज बताओ (हिंदी में)।"
                response = model.generate_content([prompt, {'mime_type': file.content_type, 'data': img_bytes}])
                diagnosis_result = response.text
            except Exception as e:
                diagnosis_result = f"Error: {str(e)}"
    return render_template('plant_disease.html', diagnosis_result=diagnosis_result, uploaded_image_b64=uploaded_image_b64)

# C. चैटबॉट API (फिक्स्ड)
@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    try:
        user_message = request.json.get('message')
        if not user_message: return jsonify({'error': 'Empty'})
        
        # स्मार्ट मॉडल सेलेक्शन
        selected_model = get_best_model()
        model = genai.GenerativeModel(selected_model)
        
        response = model.generate_content(f"किसान सहायक के रूप में हिंदी में जवाब दें: {user_message}")
        return jsonify({'answer': response.text})
    except Exception as e:
        print(f"Chatbot Error: {e}")
        if "429" in str(e):
             return jsonify({'answer': 'AI सेवा अभी व्यस्त है (कोटा फुल)। कृपया 1 मिनट बाद पूछें।'})
        return jsonify({'answer': f'AI एरर: {str(e)}'})


# --- 6. अन्य टूल्स ---

@app.route('/get-weather', methods=['POST'])
def get_weather():
    data = request.json
    city = data.get('city')
    
    weather_api_key = app.config['OPENWEATHER_API_KEY']
    
    if not weather_api_key:
        return jsonify({'error': 'Weather API Key सर्वर पर सेट नहीं है'}), 500

    if not city:
        return jsonify({'error': 'No city provided'}), 400
        
    # OpenWeatherMap API URL
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_api_key}&units=metric&lang=hi"
    
    try:
        api_response = requests.get(weather_url)
        weather_data = api_response.json()
        
        # अगर API से एरर आता है (जैसे शहर नहीं मिला)
        if api_response.status_code != 200:
            return jsonify({'error': weather_data.get('message', 'शहर नहीं मिला')}), 404
            
        # सही डेटा भेजें
        return jsonify({
            'city_name': weather_data['name'],
            'temp': weather_data['main']['temp'],
            'description': weather_data['weather'][0]['description'],
            'icon': weather_data['weather'][0]['icon'],
            'temp_max': weather_data['main']['temp_max'],
            'temp_min': weather_data['main']['temp_min'],
            'wind_speed': weather_data['wind']['speed'],
            'humidity': weather_data['main']['humidity']
        })

    except Exception as e:
        print(f"Weather Exception: {e}")
        return jsonify({'error': 'मौसम सर्वर से कनेक्ट करने में कोई समस्या हुई।'}), 500

@app.route('/soil-testing', methods=['GET', 'POST'])
@login_required
def soil_testing():
    if request.method == 'POST':
        sample_id = request.form.get('sample_id')
        if sample_id:
            db.session.add(SoilSample(sample_id=sample_id, user_id=current_user.id))
            db.session.commit()
            flash('सैंपल जमा हो गया!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('soil_testing.html')


# --- 7. वेबसाइट पेज ---

@app.route('/')
def home(): return render_template('index.html')
@app.route('/contact')
def contact(): return render_template('contact.html')
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/gallery')
def gallery(): return render_template('gallery.html')
@app.route('/schemes')
def schemes(): return render_template('schemes.html')
@app.route('/krishi-yantra')
def krishi_yantra(): return render_template('krishi_yantra.html')
@app.route('/modern-farming')
def modern_farming(): return render_template('modern_pfarming.html')
@app.route('/fertilizer-id')
def fertilizer_id(): return render_template('fertilizer_id.html')
@app.route('/weather')
def weather(): return render_template('weather.html')
@app.route('/market-prices')
def market_prices(): return render_template('market_prices.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)