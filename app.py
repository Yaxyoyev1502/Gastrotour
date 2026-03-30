import os, sqlite3, json
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from deep_translator import GoogleTranslator
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'gastro_pro_2026_final'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
LANGS = ['uz', 'ru', 'en', 'tr', 'fr', 'de', 'es', 'it', 'jp', 'cn']

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    # Render'dagi DATABASE_URL ni tekshiramiz
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Agar serverda bo'lsak, PostgreSQL'ga ulanamiz
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    else:
        # Agar o'z kompyuterimizda bo'lsak, SQLite'da davom etamiz
        import sqlite3
        conn = sqlite3.connect('gastrotour.db')
        conn.row_factory = sqlite3.Row
        return conn

@app.template_filter('from_json')
def from_json_filter(value):
    try: return json.loads(value) if value else {}
    except: return {}

def load_static_trans():
    try:
        with open('translations.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

@app.route('/')
def index():
    conn = get_db_connection()
    settings = conn.execute('SELECT * FROM site_settings WHERE id = 1').fetchone()
    countries = conn.execute('SELECT * FROM countries ORDER BY id DESC LIMIT 3').fetchall()
    festivals = conn.execute('SELECT * FROM festivals ORDER BY id DESC LIMIT 2').fetchall()
    conn.close()
    return render_template('index.html', countries=countries, festivals=festivals, settings=settings, static_trans=load_static_trans(), langs=LANGS)

@app.route('/tours')
def all_tours():
    q = request.args.get('q', '').lower()
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM countries').fetchall()
    if q: items = [i for i in items if q in i['translations'].lower()]
    conn.close()
    return render_template('tours.html', items=items, static_trans=load_static_trans(), langs=LANGS)

@app.route('/festivals')
def all_festivals():
    q = request.args.get('q', '').lower()
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM festivals').fetchall()
    if q: items = [i for i in items if q in i['translations'].lower()]
    conn.close()
    return render_template('festivals.html', items=items, static_trans=load_static_trans(), langs=LANGS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == '123':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    countries = conn.execute('SELECT * FROM countries').fetchall()
    festivals = conn.execute('SELECT * FROM festivals').fetchall()
    settings = conn.execute('SELECT * FROM site_settings WHERE id = 1').fetchone()
    conn.close()
    return render_template('admin.html', countries=countries, festivals=festivals, settings=settings, langs=LANGS)

@app.route('/admin/add/<type>', methods=['POST'])
def add_item(type):
    table = 'countries' if type == 'tour' else 'festivals'
    m_name, m_tag, m_desc = request.form.get('name_uz'), request.form.get('tag_uz'), request.form.get('desc_uz')
    trans = {}
    for l in LANGS:
        try:
            trans[l] = {
                'name': GoogleTranslator(source='uz', target=l).translate(m_name),
                'tag': GoogleTranslator(source='uz', target=l).translate(m_tag),
                'desc': GoogleTranslator(source='uz', target=l).translate(m_desc)
            }
        except: trans[l] = {'name': m_name, 'tag': m_tag, 'desc': m_desc}
    files = request.files.getlist('images')
    imgs = []
    for f in files:
        if f:
            name = f"{os.urandom(2).hex()}_{secure_filename(f.filename)}"
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
            imgs.append(name)
    conn = get_db_connection()
    conn.execute(f'INSERT INTO {table} (translations, images_json) VALUES (?, ?)', (json.dumps(trans), json.dumps(imgs)))
    conn.commit(); conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['POST'])
def update_settings():
    conn = get_db_connection()
    file = request.files.get('hero_media')
    if file:
        name = f"hero_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
        conn.execute('UPDATE site_settings SET hero_media = ? WHERE id = 1', (name,))
    about_uz = request.form.get('about_uz')
    about_trans = {l: GoogleTranslator(source='uz', target=l).translate(about_uz) if about_uz else "" for l in LANGS}
    conn.execute('UPDATE site_settings SET about_translations = ? WHERE id = 1', (json.dumps(about_trans),))
    conn.commit(); conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<type>/<int:id>')
def delete_item(type, id):
    table = 'countries' if type == 'tour' else 'festivals'
    conn = get_db_connection()
    conn.execute(f'DELETE FROM {table} WHERE id = ?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)