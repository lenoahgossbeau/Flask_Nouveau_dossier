# -----------------------------
# Imports
# -----------------------------
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
import os
import re
from datetime import datetime
from PIL import Image  # Pillow pour le traitement des images
import os

# -----------------------------
# Initialisation Flask
# -----------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret') # ⚠️ changer en production

# -----------------------------
# Configuration MongoDB
# -----------------------------
app.config['MONGO_URI'] = os.environ.get('MONGO_URI')
mongo = PyMongo(app)

# -----------------------------
# Configuration Upload photo
# -----------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'photos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Crée le dossier s'il n'existe pas
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Vérifie si l'extension du fichier est autorisée"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -----------------------------
# Route REGISTER (inscription)
# -----------------------------
@app.route('/pythonlogin/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip()

        # Validations basiques et feedback utilisateur
        if not username or not password or not email:
            flash("❌ Veuillez remplir tous les champs !", "error")
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash("❌ Adresse e-mail invalide !", "error")
        elif not re.match(r'^[A-Za-z0-9]+$', username):
            flash("❌ Le nom d'utilisateur ne doit contenir que des lettres et des chiffres !", "error")
        elif mongo.db.accounts.find_one({'username': username}):
            flash("❌ Ce nom d'utilisateur existe déjà !", "error")
        else:
            hashed_password = generate_password_hash(password)
            user_data = {
                'username': username,
                'password': hashed_password,
                'email': email,
                'photo': None,
                'phone': '',
                'address': '',
                'role': 'user',
                'created_at': datetime.now()
            }
            mongo.db.accounts.insert_one(user_data)
            flash("✅ Inscription réussie ! Vous pouvez maintenant vous connecter.", "success")

    return render_template('register.html')

# -----------------------------
# Route LOGIN (connexion)
# -----------------------------
@app.route('/pythonlogin/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Cas spécial admin (compte local simple)
        if username == 'admin' and password == 'admin123':
            session['loggedin'] = True
            session['id'] = 'admin'
            session['username'] = 'admin'
            session['role'] = 'admin'
            session['email'] = 'admin@admin.com'
            session['phone'] = ''
            session['address'] = ''
            session['photo'] = None
            return redirect(url_for('dashboard'))

        # Auth standard utilisateur
        user = mongo.db.accounts.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user.get('role', 'user')
            session['email'] = user.get('email', '')
            session['phone'] = user.get('phone', '')
            session['address'] = user.get('address', '')
            session['photo'] = user.get('photo', None)
            return redirect(url_for('home'))
        else:
            flash("❌ Nom d'utilisateur ou mot de passe incorrect.", "error")

    return render_template('index.html')

# -----------------------------
# Route LOGOUT (déconnexion)
# -----------------------------
@app.route('/pythonlogin/logout')
def logout():
    session.clear()
    flash("✅ Déconnexion réussie.", "success")
    return redirect(url_for('login'))

# -----------------------------
# Route HOME (page d'accueil)
# -----------------------------
@app.route('/pythonlogin/home')
def home():
    if 'loggedin' in session:
        return render_template('home.html', username=session['username'])
    return redirect(url_for('login'))

# -----------------------------
# Route PROFILE (profil utilisateur) — finale et alignée avec profil.html
# -----------------------------
@app.route('/pythonlogin/profile', methods=['GET', 'POST'])
def profile():
    if 'loggedin' not in session:
        flash("❌ Vous devez être connecté.", "error")
        return redirect(url_for('login'))

    # Récupération des informations (admin via session, users via MongoDB)
    if session['id'] == 'admin':
        account = {
            'username': session.get('username'),
            'email': session.get('email'),
            'phone': session.get('phone'),
            'address': session.get('address'),
            'photo': session.get('photo')
        }
    else:
        user = mongo.db.accounts.find_one({'_id': ObjectId(session['id'])})
        if not user:
            flash("❌ Utilisateur introuvable.", "error")
            return redirect(url_for('logout'))
        account = {
            'username': user.get('username'),
            'email': user.get('email'),
            'phone': user.get('phone'),
            'address': user.get('address'),
            'photo': user.get('photo')
        }

    # Soumission du formulaire "infos" (téléphone + adresse)
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        # Mise à jour des données (session pour admin, MongoDB pour users)
        if session['id'] == 'admin':
            session['phone'] = phone
            session['address'] = address
            account['phone'] = phone
            account['address'] = address
            flash("✅ Informations mises à jour avec succès !", "success")
        else:
            mongo.db.accounts.update_one(
                {'_id': ObjectId(session['id'])},
                {'$set': {'phone': phone, 'address': address}}
            )
            session['phone'] = phone
            session['address'] = address
            account['phone'] = phone
            account['address'] = address
            flash("✅ Informations mises à jour avec succès !", "success")

    # Rendu du template avec l'objet account pour l'affichage
    return render_template('profil.html', account=account)

# -----------------------------
# Route UPDATE PHOTO (upload + recadrage/redimensionnement)
# -----------------------------
@app.route('/pythonlogin/update_photo', methods=['POST'])
def update_photo():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    # Validation du fichier
    if 'photo' not in request.files:
        flash("❌ Aucun fichier reçu.", "error")
        return redirect(url_for('profile'))

    file = request.files['photo']
    if file.filename == '':
        flash("❌ Aucun fichier sélectionné.", "error")
        return redirect(url_for('profile'))

    if not allowed_file(file.filename):
        flash("❌ Format non autorisé.", "error")
        return redirect(url_for('profile'))

    try:
        # Nom de fichier unique (JPEG normalisé)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{session['username']}_{timestamp}.jpg"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        # Traitement image avec Pillow : recadrage carré centré + resize 300x300 + qualité 85
        # Ouvrir l'image depuis le fichier sauvegardé
        image = Image.open(file)
        image = image.convert("RGB")
        # Récupéré la largeur et la hauteur
        width, height = image.size
        # Déterminer le côté le plus petit pour faire un crop carré
        min_side = min(width, height)
        # Calculer les coordonées du crop centré
        left = (width - min_side) / 2
        top = (height - min_side) / 2
        right = (width + min_side) / 2
        bottom = (height + min_side) / 2
        # Rogner l'image au carré
        image = image.crop((left, top, right, bottom))
        # Redimensionner à 300x300
        image = image.resize((300, 300))
        # Sauvegarder en JPEG optimisé
        image.save(file_path, "JPEG", quality=85)

        # Nettoyage ancienne photo et mise à jour DB/session
        if session['id'] == 'admin':
            old_photo = session.get('photo')
            if old_photo:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_photo)
                if os.path.exists(old_path):
                    os.remove(old_path)
            session['photo'] = unique_filename
        else:
            user = mongo.db.accounts.find_one({'_id': ObjectId(session['id'])})
            if user and user.get('photo'):
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], user['photo'])
                if os.path.exists(old_path):
                    os.remove(old_path)

            mongo.db.accounts.update_one(
                {'_id': ObjectId(session['id'])},
                {'$set': {'photo': unique_filename}}
            )
            session['photo'] = unique_filename

        flash("✅ Photo redimensionnée et mise à jour avec succès.", "success")

    except Exception as e:
        # Log simple côté console + feedback utilisateur
        print("Erreur upload :", e)
        flash(f"❌ Erreur upload : {e}", "error")

    return redirect(url_for('profile'))

# -----------------------------
# Route TEST PHOTO (diagnostic)
# -----------------------------
@app.route('/pythonlogin/test_photo')
def test_photo():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    files_in_folder = os.listdir(app.config['UPLOAD_FOLDER'])

    if session['id'] != 'admin':
        user = mongo.db.accounts.find_one({'_id': ObjectId(session['id'])})
        user_photo = user.get('photo') if user else None
    else:
        user_photo = session.get('photo')

    # Petit rendu HTML pour diagnostiquer les chemins et la cohérence
    return f"""
    <h2>Diagnostic Photo</h2>
    <p>Session (photo): {session.get('photo')}</p>
    <p>MongoDB (photo): {user_photo}</p>
    <p>Fichiers dans le dossier /static/photos: {files_in_folder}</p>
    """

# -----------------------------
# Route DASHBOARD (admin)
# -----------------------------
@app.route('/pythonlogin/dashboard')
def dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    users = list(mongo.db.accounts.find())
    total_users = len(users)
    users_with_photos = len([u for u in users if u.get('photo')])

    return render_template(
        'dashboard.html',
        users=users,
        total_users=total_users,
        users_with_photos=users_with_photos
    )

# -----------------------------
# Route DELETE USER (admin)
# -----------------------------
@app.route('/pythonlogin/delete_user/<user_id>')
def delete_user(user_id):
    if 'loggedin' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    user = mongo.db.accounts.find_one({'_id': ObjectId(user_id)})

    # Supprime la photo liée si elle existe
    if user and user.get('photo'):
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], user['photo'])
        if os.path.exists(photo_path):
            os.remove(photo_path)

    mongo.db.accounts.delete_one({'_id': ObjectId(user_id)})
    flash("✅ Utilisateur supprimé avec succès.", "success")

    return redirect(url_for('dashboard'))


# -----------------------------
# Route TESTDB (connexion MongoDB)
# -----------------------------
@app.route('/testdb')
def testdb():
    try:
        # Insertion d’un document de test
        mongo.db.test.insert_one({'ok': True, 'timestamp': datetime.now()})
        # Lecture du document inséré
        doc = mongo.db.test.find_one({'ok': True})
        return f"""
        <h2>✅ Connexion MongoDB réussie</h2>
        <p>Document inséré : {doc}</p>
        """
    except Exception as e:
        # Affichage de l’erreur si la connexion échoue
        return f"""
        <h2>❌ Erreur MongoDB</h2>
        <pre>{e}</pre>
        """


# -----------------------------
# Lancement de l'application
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
