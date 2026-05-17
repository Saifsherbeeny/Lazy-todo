from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask import session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'lazy_secret_key_123'
# This tells Flask where the database file will live on your Mac
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data_v2.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
# This is our 'Model' - it's the Python version of that Table Blueprint
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
    # NEW LINE: Tracks if this task belongs to a grouped routine
    routine_name = db.Column(db.String(100), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

#AAAAAA

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if email already exists
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            return "Email already registered!", 400
            
        # Hash the password for security before saving
        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(email=email, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user) # Automatically log them in after signing up
        return redirect(url_for('home'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and password matches the hash
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


#AAAAAAAAA
@app.route('/inject-routine/<string:routine_type>')
@login_required
def inject_routine(routine_type):
    # Map raw types to display names
    names = {
        'morning': '☀️ Morning Routine',
        'night': '🌙 Night Routine',
        'travel': '✈️ Travel Prep'
    }
    
    routines = {
        'morning': [
            {"content": "Drink a big glass of water", "category": "Health"},
            {"content": "Check OATH app for shift updates", "category": "Work"},
            {"content": "Review today's MIASHS lectures", "category": "Uni"}
        ],
        'night': [
            {"content": "5-minute stretch & wind down", "category": "Health"},
            {"content": "Pack bag for uni tomorrow", "category": "Uni"},
            {"content": "Put phone on charger away from bed", "category": "General"}
        ],
        'travel': [
            {"content": "Double-check passport & ID", "category": "Travel"},
            {"content": "Charge phone and power bank to 100%", "category": "Travel"},
            {"content": "Pack headphones and charger", "category": "Travel"}
        ]
    }
    
    if routine_type in routines:
        for task_data in routines[routine_type]:
            new_task = Task(
                content=task_data["content"],
                category=task_data["category"],
                due_date=datetime.now().strftime('%Y-%m-%d'),
                user_id=current_user.id,
                routine_name=names[routine_type] # Group them together!
            )
            db.session.add(new_task)
        db.session.commit()
        
    return redirect(url_for('home'))
@app.route('/delete-routine/<string:routine_name>')
@login_required
def delete_routine(routine_name):
    # Find all tasks belonging to this user that match the selected routine name
    tasks_to_delete = Task.query.filter_by(user_id=current_user.id, routine_name=routine_name).all()
    
    for task in tasks_to_delete:
        db.session.delete(task)
        
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/add-custom-routine', methods=['POST'])
@login_required
def add_custom_routine():
    custom_name = request.form.get('custom_routine_name')
    raw_tasks = request.form.get('custom_tasks') # Expected to be comma-separated strings
    
    if custom_name and raw_tasks:
        # Split the text by commas and clean up white spaces
        task_list = [t.strip() for t in raw_tasks.split(',') if t.strip()]
        
        for task_content in task_list:
            new_task = Task(
                content=task_content,
                category="Custom",
                due_date=datetime.now().strftime('%Y-%m-%d'),
                user_id=current_user.id,
                routine_name=custom_name # Ties them to the custom header name
            )
            db.session.add(new_task)
            
        db.session.commit()
        
    return redirect(url_for('home'))

@app.route('/')
@login_required # Anyone trying to sneak in will be bounced to the login page
def home():
    # Only get tasks where user_id matches the logged-in user
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', tasks=all_tasks)

@app.route('/add', methods=['POST'])
@login_required
def add_task():
    task_text = request.form.get('new_task')
    due_date = request.form.get('due_date')
    due_time = request.form.get('due_time')
    category = request.form.get('category', 'General')
    
    if task_text:
        new_task = Task(
            content=task_text, 
            due_date=due_date, 
            due_time=due_time, 
            category=category,
            user_id=current_user.id # Assigns to the logged-in user
        )
        db.session.add(new_task)
        db.session.commit()
        
    return redirect(url_for('home'))

# Complete task
@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    # Use the session to find the task by ID
    task = db.session.get(Task, task_id)
    
    if task:
        task.is_done = True
        
        if task.due_date:
            today = datetime.now().date()
            due = datetime.strptime(task.due_date, '%Y-%m-%d').date()
            
            if today < due:
                task.status_message = "Early! Look at you being productive."
            elif today > due:
                task.status_message = "Late... as expected for a lazy person."
            else:
                task.status_message = "On time. Barely."
        
        db.session.commit()
        
    return redirect(url_for('home', confetti='true'))

@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = Task.query.get_or_404(id)
    db.session.delete(task_to_delete)
    db.session.commit()
    return redirect('/')

with app.app_context():
    db.create_all()
if __name__ == '__main__':
    app.run(debug=True)