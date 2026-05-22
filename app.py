from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import random
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
import requests as http_req
from flask_wtf.csrf import CSRFProtect, csrf_exempt

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'local-fallback-key')
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.sqlite'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# TODO: re-add CSRFProtect and Talisman before production deployment

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# --- CONSTANTS ---

ROUTINE_NAMES = {
    'morning': '☀️ Morning Routine',
    'night':   '🌙 Night Routine',
    'travel':  '✈️ Travel Prep',
}

ROUTINES = {
    'morning': [
        {"content": "Drink a big glass of water",         "category": "Health"},
        {"content": "Avoid socials and entertainment",    "category": "Health"},
        {"content": "5-minute stretch",                   "category": "Health"},
        {"content": "Brush teeth and wash up",            "category": "Health"},
        {"content": "Reflect",                            "category": "Mind"},
        {"content": "Make breakfast",                     "category": "Health"},
        {"content": "Check OATH app for shift updates",   "category": "Work"},
        {"content": "Review this week's lectures",        "category": "Uni"},
    ],
    'night': [
        {"content": "5-minute stretch & wind down",       "category": "Health"},
        {"content": "Pack bag for uni tomorrow",          "category": "Uni"},
        {"content": "Glass of water next to bed",         "category": "Health"},
        {"content": "Set alarms for tomorrow",            "category": "Work"},
        {"content": "Put phone on charger away from bed", "category": "General"},
    ],
    'travel': [
        {"content": "Double-check passport & ID",         "category": "Travel"},
        {"content": "Check visa requirements",            "category": "Travel"},
        {"content": "Double-check transportation",        "category": "Travel"},
        {"content": "Charge phone and power bank to 100%","category": "Travel"},
        {"content": "Pack headphones and charger",        "category": "Travel"},
        {"content": "Double-check packed bags",           "category": "Travel"},
    ],
}

WISDOM_QUOTES = [
    {"text": "Observation is a passive science, experimentation an active science.", "author": "Claude Bernard"},
    {"text": "An unexamined life is not worth living.", "author": "Socrates"},
    {"text": "Nature does not hurry, yet everything is accomplished.", "author": "Lao Tzu"},
    {"text": "It is not that I am so smart, it is just that I stay with problems longer.", "author": "Albert Einstein"},
    {"text": "The major value in life is not what you get. The major value in life is what you become.", "author": "Jim Rohn"},
    {"text": "The secret of getting ahead is getting started.", "author": "Mark Twain"},
    {"text": "He who has a why to live can bear almost any how.", "author": "Friedrich Nietzsche"},
    {"text": "We are what we repeatedly do. Excellence, then, is not an act, but a habit.", "author": "Aristotle"},
    {"text": "Concentrate all your thoughts upon the work at hand. The sun's rays do not burn until brought to a focus.", "author": "Alexander Graham Bell"},
    {"text": "It always seems impossible until it's done.", "author": "Nelson Mandela"},
    {"text": "True wealth is the wealth of the soul.", "author": "Prophet Muhammad"},
    {"text": "The mind is everything. What you think you become.", "author": "Buddha"},
    {"text": "Commit your actions to the Lord, and your plans will succeed.", "author": "Proverbs 16:3"},
    {"text": "You have a right to perform your prescribed duty, but you are not entitled to the fruits of action.", "author": "Bhagavad Gita"},
    {"text": "Waste no more time arguing about what a good man should be. Be one.", "author": "Marcus Aurelius"},
]


# --- MODELS ---

class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    email    = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    tasks    = db.relationship('Task', backref='owner_user', lazy=True)

class Task(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    content           = db.Column(db.String(200), nullable=False)
    category          = db.Column(db.String(50), default='General')
    due_date          = db.Column(db.String(50))
    due_time          = db.Column(db.String(50))
    is_done           = db.Column(db.Boolean, default=False)
    status_message    = db.Column(db.String(200), default="")
    user_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    routine_name      = db.Column(db.String(100), nullable=True)
    # 'oath' = self-sworn completion | 'photo' = AI photo verification required
    verification_type = db.Column(db.String(10), default='oath', nullable=False, server_default='oath')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _completion_status(due_date_str):
    if not due_date_str:
        return "Done... respect."
    try:
        today = datetime.now().date()
        due = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        if today < due:
            return "Early! Look at you being productive."
        elif today > due:
            return "Late... do better."
        else:
            return "On time... respect."
    except ValueError:
        return "Done... respect."

def _make_guest_task(content, category, due_date="", due_time="", routine_name=None, verification_type="oath"):
    """Returns a guest task dict with default values."""
    return {
        "id":                random.randint(100000, 999999),
        "content":           content,
        "category":          category,
        "due_date":          due_date,
        "due_time":          due_time,
        "is_done":           False,
        "status_message":    "",
        "routine_name":      routine_name,
        "verification_type": verification_type,
    }


# --- AUTHENTICATION ROUTES ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            return "Email already registered!", 400

        new_user = User(email=email, password=generate_password_hash(password, method='scrypt'))
        db.session.add(new_user)
        db.session.commit()

        # Migrate any guest session tasks into the new account
        if 'guest_tasks' in session:
            for g in session['guest_tasks']:
                db.session.add(Task(
                    content=g['content'],
                    category=g['category'],
                    due_date=g['due_date'],
                    due_time=g['due_time'],
                    is_done=g['is_done'],
                    status_message=g['status_message'],
                    routine_name=g['routine_name'],
                    verification_type=g.get('verification_type', 'oath'),
                    user_id=new_user.id,
                ))
            db.session.commit()
            session.pop('guest_tasks', None)

        login_user(new_user)
        return redirect(url_for('home'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        user     = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        return "Invalid credentials!", 401

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- MAIN HOME ---

@app.route('/')
def home():
    if 'guest_tasks' not in session:
        session['guest_tasks'] = []

    if current_user.is_authenticated:
        tasks        = Task.query.filter_by(user_id=current_user.id).all()
        display_name = current_user.email
        is_guest     = False
    else:
        tasks        = session['guest_tasks']
        display_name = "guest@oath.app"
        is_guest     = True

    return render_template(
        'index.html',
        tasks=tasks,
        name=display_name,
        is_guest=is_guest,
        wisdom=random.choice(WISDOM_QUOTES),
    )


# --- ROUTINE MANAGEMENT ROUTES ---

@app.route('/inject-routine/<string:routine_type>')
def inject_routine(routine_type):
    if routine_type not in ROUTINES:
        return redirect(url_for('home'))

    today      = datetime.now().strftime('%Y-%m-%d')
    name       = ROUTINE_NAMES[routine_type]
    task_list  = ROUTINES[routine_type]

    if current_user.is_authenticated:
        for t in task_list:
            db.session.add(Task(
                content=t['content'],
                category=t['category'],
                due_date=today,
                user_id=current_user.id,
                routine_name=name,
                verification_type='oath',
            ))
        db.session.commit()
    else:
        for t in task_list:
            session['guest_tasks'].append(
                _make_guest_task(t['content'], t['category'], due_date=today, routine_name=name)
            )
        session.modified = True

    return redirect(url_for('home'))


@app.route('/delete-routine/<string:routine_name>')
def delete_routine(routine_name):
    if current_user.is_authenticated:
        for task in Task.query.filter_by(user_id=current_user.id, routine_name=routine_name).all():
            db.session.delete(task)
        db.session.commit()
    else:
        session['guest_tasks'] = [t for t in session['guest_tasks'] if t['routine_name'] != routine_name]
        session.modified = True

    return redirect(url_for('home'))


@app.route('/add-custom-routine', methods=['POST'])
def add_custom_routine():
    custom_name = request.form.get('custom_routine_name')
    raw_tasks   = request.form.get('custom_tasks')

    if not (custom_name and raw_tasks):
        return redirect(url_for('home'))

    today     = datetime.now().strftime('%Y-%m-%d')
    task_list = [t.strip() for t in raw_tasks.split(',') if t.strip()]

    if current_user.is_authenticated:
        for content in task_list:
            db.session.add(Task(
                content=content,
                category='Custom',
                due_date=today,
                user_id=current_user.id,
                routine_name=custom_name,
                verification_type='oath',
            ))
        db.session.commit()
    else:
        for content in task_list:
            session['guest_tasks'].append(
                _make_guest_task(content, 'Custom', due_date=today, routine_name=custom_name)
            )
        session.modified = True

    return redirect(url_for('home'))


@app.route('/add-to-routine/<string:routine_name>', methods=['POST'])
def add_to_routine(routine_name):
    content = request.form.get('routine_task_content')

    if not content:
        return redirect(url_for('home'))

    today = datetime.now().strftime('%Y-%m-%d')

    if current_user.is_authenticated:
        db.session.add(Task(
            content=content,
            category='Custom Item',
            due_date=today,
            user_id=current_user.id,
            routine_name=routine_name,
            verification_type='oath',
        ))
        db.session.commit()
    else:
        session['guest_tasks'].append(
            _make_guest_task(content, 'Custom Item', due_date=today, routine_name=routine_name)
        )
        session.modified = True

    return redirect(url_for('home'))


# --- SINGLE TASK ROUTES ---

@app.route('/add', methods=['POST'])
def add_task():
    content           = request.form.get('new_task')
    due_date          = request.form.get('due_date')
    due_time          = request.form.get('due_time')
    category          = request.form.get('category', 'General')
    verification_type = request.form.get('verification_type', 'oath')

    if not content:
        return redirect(url_for('home'))

    if current_user.is_authenticated:
        db.session.add(Task(
            content=content,
            due_date=due_date,
            due_time=due_time,
            category=category,
            user_id=current_user.id,
            verification_type=verification_type,
        ))
        db.session.commit()
    else:
        session['guest_tasks'].append(
            _make_guest_task(
                content, category,
                due_date=due_date or "",
                due_time=due_time or "",
                verification_type=verification_type,
            )
        )
        session.modified = True

    return redirect(url_for('home'))


@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    if current_user.is_authenticated:
        task = db.session.get(Task, task_id)
        if task:
            task.is_done        = True
            task.status_message = _completion_status(task.due_date)
            db.session.commit()
    else:
        for task in session['guest_tasks']:
            if task['id'] == task_id:
                task['is_done']        = True
                task['status_message'] = _completion_status(task['due_date'])
                break
        session.modified = True

    return redirect(url_for('home', confetti='true'))


@app.route('/delete/<int:id>')
def delete(id):
    if current_user.is_authenticated:
        task = db.session.get(Task, id)
        if task:
            db.session.delete(task)
            db.session.commit()
    else:
        session['guest_tasks'] = [t for t in session['guest_tasks'] if t['id'] != id]
        session.modified = True

    return redirect(url_for('home'))


# --- AI PHOTO VERIFICATION ---

@app.route('/verify-photo/<int:task_id>', methods=['POST'])
@csrf_exempt
def verify_photo(task_id):
    """
    Receives a base64 image from the frontend, sends it to OpenAI Vision,
    and returns JSON { confirmed: bool, reason: str }.
    """
    openai_key = os.environ.get('OPENAI_API_KEY')
    if not openai_key:
        return jsonify({'error': 'AI verification is not configured on this server.'}), 503

    data       = request.get_json(silent=True) or {}
    image_b64  = data.get('image', '')

    if not image_b64:
        return jsonify({'error': 'No image received.'}), 400

    # Get the task description (works for both auth users and guests)
    task_content = "an unknown task"
    if current_user.is_authenticated:
        task = db.session.get(Task, task_id)
        if task:
            task_content = task.content
    else:
        for t in session.get('guest_tasks', []):
            if t['id'] == task_id:
                task_content = t['content']
                break

    prompt = (
        f'The user says they completed this task: "{task_content}". '
        'Does this photo reasonably prove it? '
        'Be fairly lenient — everyday evidence is fine. '
        'You must respond in exactly this JSON format:\n'
        '{\n'
        '  "confirmed": true,\n'
        '  "reason": "Your single sentence explanation here."\n'
        '}\n'
        'Respond with raw JSON only. Do not include markdown formatting or blocks.'
    )

    try:
        resp = http_req.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {openai_key}',
                'Content-Type':  'application/json',
            },
            json={
                'model':      'gpt-4o-mini',
                'max_tokens': 120,
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {
                            'type':      'image_url',
                            'image_url': {
                                'url':    f'data:image/jpeg;base64,{image_b64}',
                                'detail': 'low',
                            }
                        },
                    ]
                }]
            },
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        return jsonify({'error': f'AI service error: {str(e)}'}), 502

    raw = resp.json()['choices'][0]['message']['content'].strip()

    # Strip any accidental markdown fences
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: if we can't parse, be lenient
        result = {'confirmed': True, 'reason': 'Verification accepted.'}

    return jsonify(result)


# --- ACCOUNT & PRIVACY ROUTES ---

@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = db.session.get(User, current_user.id)
    Task.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    logout_user()
    return redirect(url_for('login'))


@app.route('/export-data')
@login_required
def export_data():
    import csv
    import io
    from flask import Response

    tasks = Task.query.filter_by(user_id=current_user.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['content', 'category', 'due_date', 'due_time', 'is_done', 'status_message', 'routine_name', 'verification_type'])
    for t in tasks:
        writer.writerow([t.content, t.category, t.due_date, t.due_time, t.is_done, t.status_message, t.routine_name, t.verification_type])
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=oath-data-{current_user.email}.csv'}
    )


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


with app.app_context():
    db.create_all()
    print("✅ Database tables verified.", flush=True)

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')