from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# This tells Flask where the database file will live on your Mac
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# This is our 'Model' - it's the Python version of that Table Blueprint
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='General')
    due_date = db.Column(db.String(50))
    due_time = db.Column(db.String(50))
    is_done = db.Column(db.Boolean, default=False)
    status_message = db.Column(db.String(200), default="")

@app.route('/')
def home():
    all_tasks = Task.query.all()  # This gets all the tasks from the database
    return render_template('index.html', tasks=all_tasks)

@app.route('/add', methods=['POST'])
def add_task():
    task_text = request.form.get('new_task')
    due_date = request.form.get('due_date')
    due_time = request.form.get('due_time')
    category = request.form.get('category', 'General')
    
    if task_text:
        # 1. Create the object
        new_task = Task(
            content=task_text, 
            due_date=due_date, 
            due_time=due_time, 
            category=category
        )
        # 2. Add it to the 'session' (like putting it in the checkout basket)
        db.session.add(new_task)
        # 3. Commit it (like hitting 'Pay' to make it official)
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
with app.app_context():
    db.create_all()
if __name__ == '__main__':
    app.run(debug=True)