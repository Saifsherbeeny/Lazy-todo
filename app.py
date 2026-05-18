from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import random
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import sys

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'local-fallback-key')
app.config['SESSION_COOKIE_SECURE'] = False  # temporarily off
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# temporarily remove CSRFProtect and Talisman entirely to avoid testing headaches, will re-add before production deployment
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    tasks = db.relationship('Task', backref='owner_user', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='General')
    due_date = db.Column(db.String(50))
    due_time = db.Column(db.String(50))
    is_done = db.Column(db.Boolean, default=False)
    status_message = db.Column(db.String(200), default="")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 
    routine_name = db.Column(db.String(100), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- AUTHENTICATION ROUTES ---

@app.route('/test')
def test():
    return "app is alive", 200

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            return "Email already registered!", 400
            
        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(email=email, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        if 'guest_tasks' in session:
            for g_task in session['guest_tasks']:
                db_task = Task(
                    content=g_task['content'],
                    category=g_task['category'],
                    due_date=g_task['due_date'],
                    due_time=g_task['due_time'],
                    is_done=g_task['is_done'],
                    status_message=g_task['status_message'],
                    routine_name=g_task['routine_name'],
                    user_id=new_user.id
                )
                db.session.add(db_task)
            db.session.commit()
            session.pop('guest_tasks', None)
        
        login_user(new_user)
        return redirect(url_for('home'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            return "Invalid credentials!", 401
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- MAIN CORE HOME ENGINE ---

@app.route('/')
def home():
    if 'guest_tasks' not in session:
        session['guest_tasks'] = []

    if current_user.is_authenticated:
        tasks = Task.query.filter_by(user_id=current_user.id).all()
        display_name = current_user.email
        is_guest = False
    else:
        tasks = session['guest_tasks']
        display_name = "guest@oath.app"
        is_guest = True

    wisdom_quotes = [
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
        {"text": "True wealth is the wealth of the soul.", "author": "Prophet Muhammad (Hadith)"},
        {"text": "The mind is everything. What you think you become.", "author": "Buddha"},
        {"text": "Commit your actions to the Lord, and your plans will succeed.", "author": "Proverbs 16:3"},
        {"text": "You have a right to perform your prescribed duty, but you are not entitled to the fruits of action.", "author": "Bhagavad Gita"},
        {"text": "Waste no more time arguing about what a good man should be. Be one.", "author": "Marcus Aurelius"}
    ]
    selected_wisdom = random.choice(wisdom_quotes)
    
    return render_template('index.html', tasks=tasks, name=display_name, is_guest=is_guest, wisdom=selected_wisdom)


# --- ROUTINE MANAGEMENT ROUTES ---

@app.route('/inject-routine/<string:routine_type>')
def inject_routine(routine_type):
    names = {'morning': '☀️ Morning Routine', 'night': '🌙 Night Routine', 'travel': '✈️ Travel Prep'}
    routines = {
        'morning': [
            {"content": "Drink a big glass of water", "category": "Health"},
            {"content": "avoid socials and entertainment", "category": "Health"},
            {"content": "5-minuute stretch", "category": "Health"},
            {"content": "brush teeth and wash up", "category": "Health"},
            {"content": "reflect", "category": "Mind"},
            {"content": "Make breakfast", "category": "Health"},
            {"content": "Check OATH app for shift updates", "category": "Work"},
            {"content": "Review this week's lectures", "category": "Uni"}
        ],
        'night': [
            {"content": "5-minute stretch & wind down", "category": "Health"},
            {"content": "Pack bag for uni tomorrow", "category": "Uni"},
            {"content": "Glass of water next to bed", "category": "Health"},
            {"content": "Set alarms for tomorrow", "category": "Work"},
            {"content": "Put phone on charger away from bed", "category": "General"}
        ],
        'travel': [
            {"content": "Double-check passport & ID", "category": "Travel"},
            {"content": "Check visa requirements", "category": "Travel"},
            {"content": "Double-check Transportation", "category": "Travel"},
            {"content": "Charge phone and power bank to 100%", "category": "Travel"},
            {"content": "Pack headphones and charger", "category": "Travel"},
            {"content": "Double-check packed bags", "category": "Travel"}
        ]
    }
    
    if routine_type in routines:
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        if current_user.is_authenticated:
            for task_data in routines[routine_type]:
                new_task = Task(
                    content=task_data["content"],
                    category=task_data["category"],
                    due_date=today_date,
                    user_id=current_user.id,
                    routine_name=names[routine_type] 
                )
                db.session.add(new_task)
            db.session.commit()
        else:
            for task_data in routines[routine_type]:
                guest_task = {
                    "id": random.randint(100000, 999999),
                    "content": task_data["content"],
                    "category": task_data["category"],
                    "due_date": today_date,
                    "due_time": "",
                    "is_done": False,
                    "status_message": "",
                    "routine_name": names[routine_type]
                }
                session['guest_tasks'].append(guest_task)
            session.modified = True
            
    return redirect(url_for('home'))

@app.route('/delete-routine/<string:routine_name>')
def delete_routine(routine_name):
    if current_user.is_authenticated:
        tasks_to_delete = Task.query.filter_by(user_id=current_user.id, routine_name=routine_name).all()
        for task in tasks_to_delete:
            db.session.delete(task)
        db.session.commit()
    else:
        session['guest_tasks'] = [t for t in session['guest_tasks'] if t['routine_name'] != routine_name]
        session.modified = True
        
    return redirect(url_for('home'))

@app.route('/add-custom-routine', methods=['POST'])
def add_custom_routine():
    custom_name = request.form.get('custom_routine_name')
    raw_tasks = request.form.get('custom_tasks')
    
    if custom_name and raw_tasks:
        task_list = [t.strip() for t in raw_tasks.split(',') if t.strip()]
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        if current_user.is_authenticated:
            for task_content in task_list:
                new_task = Task(
                    content=task_content,
                    category="Custom",
                    due_date=today_date,
                    user_id=current_user.id,
                    routine_name=custom_name
                )
                db.session.add(new_task)
            db.session.commit()
        else:
            for task_content in task_list:
                guest_task = {
                    "id": random.randint(100000, 999999),
                    "content": task_content,
                    "category": "Custom",
                    "due_date": today_date,
                    "due_time": "",
                    "is_done": False,
                    "status_message": "",
                    "routine_name": custom_name
                }
                session['guest_tasks'].append(guest_task)
            session.modified = True
            
    return redirect(url_for('home'))

@app.route('/add-to-routine/<string:routine_name>', methods=['POST'])
def add_to_routine(routine_name):
    task_content = request.form.get('routine_task_content')
    
    if task_content:
        today_date = datetime.now().strftime('%Y-%m-%d')
        if current_user.is_authenticated:
            new_task = Task(
                content=task_content,
                category="Custom Item",
                due_date=today_date,
                user_id=current_user.id,
                routine_name=routine_name
            )
            db.session.add(new_task)
            db.session.commit()
        else:
            guest_task = {
                "id": random.randint(100000, 999999),
                "content": task_content,
                "category": "Custom Item",
                "due_date": today_date,
                "due_time": "",
                "is_done": False,
                "status_message": "",
                "routine_name": routine_name
            }
            session['guest_tasks'].append(guest_task)
            session.modified = True
            
    return redirect(url_for('home'))


# --- SINGLE TASK INTERACTION ROUTES ---

@app.route('/add', methods=['POST'])
def add_task():
    task_text = request.form.get('new_task')
    due_date = request.form.get('due_date')
    due_time = request.form.get('due_time')
    category = request.form.get('category', 'General')
    
    if task_text:
        if current_user.is_authenticated:
            new_task = Task(
                content=task_text, 
                due_date=due_date, 
                due_time=due_time, 
                category=category,
                user_id=current_user.id
            )
            db.session.add(new_task)
            db.session.commit()
        else:
            guest_task = {
                "id": random.randint(100000, 999999),
                "content": task_text,
                "category": category,
                "due_date": due_date,
                "due_time": due_time,
                "is_done": False,
                "status_message": "",
                "routine_name": None
            }
            session['guest_tasks'].append(guest_task)
            session.modified = True
        
    return redirect(url_for('home'))

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    if current_user.is_authenticated:
        task = db.session.get(Task, task_id)
        if task:
            task.is_done = True
            if task.due_date:
                today = datetime.now().date()
                due = datetime.strptime(task.due_date, '%Y-%m-%d').date()
                if today < due:
                    task.status_message = "Early! Look at you being productive."
                elif today > due:
                    task.status_message = "Late... Try and do better."
                else:
                    task.status_message = "On time... respect."
            db.session.commit()
    else:
        for task in session['guest_tasks']:
            if task['id'] == task_id:
                task['is_done'] = True
                if task['due_date']:
                    today = datetime.now().date()
                    try:
                        due = datetime.strptime(task['due_date'], '%Y-%m-%d').date()
                        if today < due:
                            task['status_message'] = "Early! Look at you being productive."
                        elif today > due:
                            task['status_message'] = "Late... Try and do better."
                        else:
                            task['status_message'] = "On time... respect."
                    except:
                        task['status_message'] = "Done... respect."
                break
        session.modified = True
        
    return redirect(url_for('home', confetti='true'))

@app.route('/delete/<int:id>')
def delete(id):
    if current_user.is_authenticated:
        task_to_delete = Task.query.get_or_404(id)
        db.session.delete(task_to_delete)
        db.session.commit()
    else:
        session['guest_tasks'] = [t for t in session['guest_tasks'] if t['id'] != id]
        session.modified = True
    return redirect('/')
with app.app_context():
    db.create_all()
    print("✅ Database tables verified.", flush=True)

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')