import os
import asyncio
import uuid
import json
import threading
import copy
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, has_request_context
from ai_tutor.tutor_system import TutorSystem
from ai_tutor.tools import TutorContext

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key_for_testing')

# Global dictionary to store active tutor sessions
active_tutors = {}
# Global dictionary to store background tasks
background_tasks = {}

# Create a default storage directory in the current working directory
DEFAULT_STORAGE_DIR = os.path.join(os.getcwd(), "ai_tutor_data")
os.makedirs(DEFAULT_STORAGE_DIR, exist_ok=True)

def run_async(route_function):
    """
    Decorator to handle async functions in Flask routes by running the task in a separate thread
    and redirecting to a waiting page that polls for completion.
    """
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Store user_id and other session data in a separate variable to avoid request context issues
        user_id = session.get('user_id')
        file_paths = session.get('file_paths', [])
        learning_objective = session.get('learning_objective', '')
        
        # Create a new event loop for this task
        def run_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Get the result of the async function
                # Pass the session data as arguments to avoid accessing session in background thread
                result = loop.run_until_complete(route_function(user_id=user_id, 
                                                               file_paths=file_paths,
                                                               learning_objective=learning_objective,
                                                               *args, **kwargs))
                background_tasks[task_id] = {
                    'status': 'completed',
                    'result': result,
                    'user_id': user_id
                }
            except Exception as e:
                background_tasks[task_id] = {
                    'status': 'error',
                    'error': str(e),
                    'user_id': user_id
                }
            finally:
                loop.close()
        
        # Start the task in a background thread
        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()
        
        # Store the task information
        background_tasks[task_id] = {
            'status': 'running',
            'thread': thread,
            'user_id': user_id
        }
        
        # Store the task ID in the session
        session['task_id'] = task_id
        
        # Redirect to a waiting page
        return render_template('processing.html', 
                              task_id=task_id, 
                              next_route=route_function.__name__)
    
    return wrapper

@app.route('/')
def index():
    """Home page with options to start a new session or continue existing one"""
    return render_template('index.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Set up a new learning session"""
    if request.method == 'POST':
        # Get user ID or generate a new one
        user_id = request.form.get('user_id') or str(uuid.uuid4())
        session['user_id'] = user_id
        
        # Get storage directory or use default
        storage_dir = request.form.get('storage_dir')
        if not storage_dir:
            storage_dir = DEFAULT_STORAGE_DIR
        
        # Create a tutor instance for this user
        tutor = TutorSystem[TutorContext](
            user_id=user_id,
            storage_dir=storage_dir,
            use_sqlite=bool(request.form.get('use_sqlite'))
        )
        active_tutors[user_id] = tutor
        
        return redirect(url_for('upload_materials'))
    
    return render_template('setup.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_materials():
    """Upload learning materials"""
    user_id = session.get('user_id')
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        file_urls = request.form.get('file_urls', '').strip()
        
        if not file_urls:
            # Use sample file if none provided
            file_paths = ["https://cdn.openai.com/API/docs/deep_research_blog.pdf"]
        else:
            file_paths = [url.strip() for url in file_urls.split(',')]
        
        # Store file paths in session for the next step
        session['file_paths'] = file_paths
        return redirect(url_for('learning_objective'))
    
    return render_template('upload.html')

@app.route('/objective', methods=['GET', 'POST'])
def learning_objective():
    """Set learning objective"""
    user_id = session.get('user_id')
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        objective = request.form.get('objective', '').strip()
        
        if not objective:
            flash('Please enter a learning objective.')
            return render_template('objective.html')
        
        # Store objective in session
        session['learning_objective'] = objective
        return redirect(url_for('process_knowledge_base'))
    
    return render_template('objective.html')

@app.route('/process_knowledge_base')
def process_knowledge_base():
    """Route to initiate knowledge base setup as a background task"""
    user_id = session.get('user_id')
    file_paths = session.get('file_paths', [])
    
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    # Store data in session for the background task
    session['setup_data'] = {
        'file_paths': file_paths
    }
    
    # Redirect to the background task handler
    return redirect(url_for('setup_knowledge_base'))

@app.route('/setup_knowledge_base')
@run_async
async def setup_knowledge_base(user_id=None, file_paths=None, learning_objective=None):
    """Set up knowledge base with the provided files (runs as background task)"""
    # Use the passed parameters instead of accessing session
    if not user_id or user_id not in active_tutors:
        return {'success': False, 'next_url': url_for('index')}
    
    tutor = active_tutors[user_id]
    
    # Set up knowledge base
    result = await tutor.setup_knowledge_base(file_paths)
    
    if not result.get("file_ids"):
        return {'success': False, 'next_url': url_for('upload_materials')}
    
    return {'success': True, 'next_url': url_for('process_study_plan')}

@app.route('/process_study_plan')
def process_study_plan():
    """Route to initiate study plan creation as a background task"""
    user_id = session.get('user_id')
    learning_objective = session.get('learning_objective')
    
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    # Redirect to the background task handler
    return redirect(url_for('create_study_plan'))

@app.route('/create_study_plan')
@run_async
async def create_study_plan(user_id=None, file_paths=None, learning_objective=None):
    """Create a study plan based on the learning objective (runs as background task)"""
    # Use the passed parameters instead of accessing session
    if not user_id or user_id not in active_tutors:
        return {'success': False, 'next_url': url_for('index')}
    
    tutor = active_tutors[user_id]
    
    # Create study plan
    await tutor.create_study_plan(learning_objective)
    
    return {'success': True, 'next_url': url_for('study_plan')}

@app.route('/study_plan')
def study_plan():
    """Display the study plan and start learning"""
    user_id = session.get('user_id')
    
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    tutor = active_tutors[user_id]
    study_plan = tutor.study_plan
    
    # If no study plan, create a default one for display
    if not study_plan or not hasattr(study_plan, 'topics'):
        default_topics = ["Introduction", "Key Concepts", "Applications", "Advanced Topics"]
        default_path = default_topics.copy()
        default_time = {topic: "30 minutes" for topic in default_topics}
        
        study_plan_data = {
            'topics': default_topics,
            'learning_path': default_path,
            'estimated_time': default_time
        }
    else:
        # Convert study plan to dict for template
        study_plan_data = {
            'topics': study_plan.topics,
            'learning_path': study_plan.learning_path,
            'estimated_time': study_plan.estimated_time
        }
    
    return render_template('study_plan.html', study_plan=study_plan_data)

@app.route('/learn')
def learn():
    """Start the learning process"""
    user_id = session.get('user_id')
    
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    tutor = active_tutors[user_id]
    
    # Render the learning page, the actual process will be started via AJAX
    return render_template('learn.html', 
                          learning_objective=tutor.learning_objective,
                          user_id=user_id)

@app.route('/start_learning', methods=['POST'])
@run_async
async def start_learning(user_id=None, file_paths=None, learning_objective=None):
    """AJAX endpoint to start the learning process (runs as background task)"""
    # For this route, we get user_id from the request data if not passed from decorator
    if not user_id:
        data = request.get_json()
        user_id = data.get('user_id') if data else None
    
    if not user_id or user_id not in active_tutors:
        return {'status': 'error', 'message': 'Invalid session'}
    
    tutor = active_tutors[user_id]
    
    # Run the complete learning process
    results = await tutor.complete_learning_objective()
    
    # Return results
    return {
        'status': 'success',
        'learning_objective': tutor.learning_objective,
        'mastery_levels': tutor.mastery_levels,
        'completed': results.get('completed', False),
        'completed_topics': tutor.completed_topics
    }

@app.route('/check_task_status/<task_id>')
def check_task_status(task_id):
    """AJAX endpoint to check the status of a background task"""
    if task_id not in background_tasks:
        return jsonify({'status': 'not_found'})
    
    task = background_tasks[task_id]
    
    if task['status'] == 'running':
        return jsonify({'status': 'running'})
    elif task['status'] == 'completed':
        result = task['result']
        return jsonify({
            'status': 'completed',
            'result': result,
            'next_url': result.get('next_url')
        })
    else:  # Error
        return jsonify({
            'status': 'error',
            'message': task.get('error', 'An unknown error occurred')
        })

@app.route('/results')
def results():
    """Display final learning results"""
    user_id = session.get('user_id')
    
    if not user_id or user_id not in active_tutors:
        flash('Session expired or invalid. Please start a new session.')
        return redirect(url_for('index'))
    
    tutor = active_tutors[user_id]
    
    # Get progress data
    mastery_levels = tutor.mastery_levels or {}
    completed_topics = tutor.completed_topics or []
    
    return render_template('results.html',
                          learning_objective=tutor.learning_objective,
                          mastery_levels=mastery_levels,
                          completed_topics=completed_topics)

@app.route('/continue_session', methods=['GET', 'POST'])
def continue_session():
    """Continue an existing learning session"""
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        
        if not user_id:
            flash('Please provide a user ID.')
            return render_template('continue.html')
        
        # Get storage directory or use default
        storage_dir = request.form.get('storage_dir')
        if not storage_dir:
            storage_dir = DEFAULT_STORAGE_DIR
        
        # Create tutor instance with existing user ID
        tutor = TutorSystem[TutorContext](
            user_id=user_id,
            storage_dir=storage_dir,
            use_sqlite=bool(request.form.get('use_sqlite'))
        )
        
        # Store in active tutors and session
        active_tutors[user_id] = tutor
        session['user_id'] = user_id
        
        # If learning objective exists, go to study plan
        if tutor.learning_objective:
            return redirect(url_for('study_plan'))
        else:
            flash('No existing learning session found for this user ID.')
            return render_template('continue.html')
    
    return render_template('continue.html')

@app.route('/direct_upload', methods=['POST'])
def direct_upload():
    """Handle direct upload of documents and learning objective"""
    # Generate a user ID
    user_id = str(uuid.uuid4())
    session['user_id'] = user_id
    
    # Get file URLs and learning objective
    file_urls = request.form.get('file_urls', '').strip()
    learning_objective = request.form.get('learning_objective', '').strip()
    
    if not learning_objective:
        flash('Please enter a learning objective.')
        return redirect(url_for('index'))
    
    # Store learning objective in session
    session['learning_objective'] = learning_objective
    
    # Prepare file paths
    if not file_urls:
        # Use sample file if none provided
        file_paths = ["https://cdn.openai.com/API/docs/deep_research_blog.pdf"]
    else:
        file_paths = [url.strip() for url in file_urls.split(',')]
    
    # Store file paths in session
    session['file_paths'] = file_paths
    
    # Create a tutor instance with default storage
    tutor = TutorSystem[TutorContext](
        user_id=user_id,
        storage_dir=DEFAULT_STORAGE_DIR,
        use_sqlite=False
    )
    active_tutors[user_id] = tutor
    
    # Redirect to the knowledge base setup process
    flash('Starting the learning process. This may take a moment...')
    return redirect(url_for('process_knowledge_base'))

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Run the Flask app
    app.run(debug=True) 