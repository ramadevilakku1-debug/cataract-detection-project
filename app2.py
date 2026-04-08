import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
import io
import base64
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import re

############################################
# FLASK SETUP
############################################

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = 'users.db'

############################################
# DATABASE FUNCTIONS
############################################

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT,
            mobile_number TEXT,
            locality TEXT,
            address TEXT,
            is_active INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# Initialize DB
init_db()

############################################
# MODEL
############################################

import torch
import timm
from torchvision import transforms
import torch.nn.functional as F

device = torch.device("cpu")

model = timm.create_model(
    'vit_base_patch16_224',
    pretrained=False,
    num_classes=3
)

model.load_state_dict(torch.load('cataract_vit_model.pth', map_location=device))
model.eval()

classes = ['Immature', 'Mature', 'Normal']

############################################
# IMAGE PREPROCESSING
############################################

transform = transforms.Compose([
    transforms.Resize((224,224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5,0.5,0.5],[0.5,0.5,0.5])
])

############################################
# PREDICTION FUNCTION
############################################

def predict(image):
    image = image.convert("RGB")
    image = transform(image).unsqueeze(0)

    with torch.no_grad():
        outputs = model(image)
        probs = F.softmax(outputs, dim=1)
        confidence, predicted = torch.max(probs, 1)

    confidence = confidence.item()
    predicted_class = classes[predicted.item()]

    if confidence < 0.60:
        return "Invalid image (Not an eye image)"

    return f"{predicted_class} (Confidence: {confidence*100:.2f}%)"

############################################
# HELPER FUNCTIONS
############################################

def fetch_cataract_stats():
    return {
        "Global Prevalence": "51% of global blindness",
        "Leading Cause": "Leading cause of blindness worldwide",
        "Treatable": "Cataract is treatable with surgery"
    }

def fetch_cataract_remedies():
    return [
        "Surgical removal of the cataract",
        "Wearing sunglasses",
        "Using magnifying lenses",
        "Improving lighting"
    ]

def fetch_cataract_risks():
    return [
        "Aging", "Diabetes", "Sunlight",
        "Smoking", "Obesity", "Blood pressure"
    ]

def fetch_cataract_symptoms():
    return [
        "Blurred vision", "Night difficulty",
        "Light sensitivity", "Halos", "Color fading"
    ]

def plot_cataract_stats():
    labels = ['Cataract', 'Other Causes']
    sizes = [51, 49]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%')
    ax.axis('equal')

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img = base64.b64encode(buf.getvalue()).decode()
    plt.close(fig)
    return img

def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

############################################
# REGISTER
############################################

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']
        mobile = request.form['mobile_number']
        locality = request.form['locality']
        address = request.form['address']

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")

        pattern = r'^(?=.*[!@#$%^&*]).{8,}$'
        if not re.match(pattern, password):
            return render_template('register.html',
                                   error="Password must contain special character & 8+ length")

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO users (username, password, email, mobile_number, locality, address, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (username, generate_password_hash(password), email, mobile, locality, address))
            conn.commit()
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Username already exists")
        finally:
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

############################################
# LOGIN
############################################

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password) and user['is_active'] == 1:
            session['username'] = username
            return redirect(url_for('prediction'))
        else:
            return render_template('login.html', error="Invalid or not approved")

    return render_template('login.html')

############################################
# ADMIN LOGIN
############################################

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('admin_login.html')

############################################
# ADMIN PANEL
############################################

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    return render_template('admin.html', users=users)

############################################ 
# APPROVE USER (FIXED)
############################################

@app.route('/approve_user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    # Toggle active/inactive instead of always setting 1
    user = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    
    new_status = 0 if user['is_active'] else 1

    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()

    return redirect(url_for('admin'))

############################################
# DELETE USER (OPTIONAL)
############################################

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin'))

############################################
# PREDICTION
############################################

@app.route('/prediction', methods=['GET', 'POST'])
def prediction():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('file')

        if not file:
            return render_template('index.html', error="No file uploaded")

        try:
            img = Image.open(file.stream)
        except:
            return render_template('index.html', error="Invalid image file")

        result = predict(img)

        return render_template('index.html',
                               prediction=result,
                               uploaded_image=image_to_base64(img),
                               stats=fetch_cataract_stats(),
                               remedies=fetch_cataract_remedies(),
                               risks=fetch_cataract_risks(),
                               symptoms=fetch_cataract_symptoms(),
                               pie_chart=plot_cataract_stats())

    return render_template('index.html')

############################################
# HOME
############################################

@app.route('/')
def index():
    return render_template('home.html')














@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('admin', None)
    return redirect(url_for('login'))

############################################
# RUN
############################################

if __name__ == '__main__':
    app.run(debug=True)