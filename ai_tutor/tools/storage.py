import os
import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

class UserProgressStore:
    """
    Persistent storage for user learning progress data
    
    This class provides methods to store and retrieve user progress data,
    including study plans, mastery levels, quiz results, and learning history.
    
    Two storage backends are supported:
    1. JSON files (default) - Simple file-based storage
    2. SQLite database - More robust storage with query capabilities
    """
    
    def __init__(self, storage_dir: str = None, use_sqlite: bool = False):
        """
        Initialize the storage system
        
        Args:
            storage_dir: Directory to store data files (defaults to ~/.ai_tutor)
            use_sqlite: Whether to use SQLite instead of JSON files
        """
        # Default storage directory is in user's home directory
        if storage_dir is None:
            self.storage_dir = os.path.expanduser(os.path.join("~", ".ai_tutor"))
        else:
            self.storage_dir = storage_dir
        
        # Create the storage directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)
        
        self.use_sqlite = use_sqlite
        
        if use_sqlite:
            self.db_path = os.path.join(self.storage_dir, "user_progress.db")
            self._init_sqlite_db()
    
    def _init_sqlite_db(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            created_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_objectives (
            objective_id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            description TEXT,
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_plans (
            plan_id TEXT PRIMARY KEY,
            objective_id TEXT,
            topics TEXT,
            learning_path TEXT,
            estimated_time TEXT,
            prerequisites TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (objective_id) REFERENCES learning_objectives (objective_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS topic_progress (
            progress_id TEXT PRIMARY KEY,
            user_id TEXT,
            objective_id TEXT,
            topic TEXT,
            mastery_level REAL,
            completed BOOLEAN,
            last_studied TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (objective_id) REFERENCES learning_objectives (objective_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id TEXT PRIMARY KEY,
            user_id TEXT,
            objective_id TEXT,
            topic TEXT,
            questions TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (objective_id) REFERENCES learning_objectives (objective_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            result_id TEXT PRIMARY KEY,
            quiz_id TEXT,
            user_id TEXT,
            answers TEXT,
            score REAL,
            feedback TEXT,
            created_at TEXT,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_user_json_path(self, user_id: str) -> str:
        """Get the path to a user's JSON data file"""
        return os.path.join(self.storage_dir, f"user_{user_id}.json")
    
    def save_user_progress(self, user_id: str, data: Dict[str, Any]) -> bool:
        """
        Save all user progress data to storage
        
        Args:
            user_id: Unique identifier for the user
            data: Dictionary containing all user progress data
            
        Returns:
            True if successful, False otherwise
        """
        if self.use_sqlite:
            return self._save_to_sqlite(user_id, data)
        else:
            return self._save_to_json(user_id, data)
    
    def _save_to_json(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Save data to JSON file"""
        try:
            # Add timestamp
            data['last_updated'] = datetime.now().isoformat()
            
            # Save to file
            file_path = self._get_user_json_path(user_id)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving user progress to JSON: {e}")
            return False
    
    def _save_to_sqlite(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Save data to SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Make sure user exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (user_id, created_at) VALUES (?, ?)",
                    (user_id, datetime.now().isoformat())
                )
            
            # Extract learning objectives
            if 'learning_objectives' in data:
                for obj_id, obj_data in data['learning_objectives'].items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO learning_objectives 
                        (objective_id, user_id, title, description, created_at, completed_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            obj_id,
                            user_id,
                            obj_data.get('title', ''),
                            obj_data.get('description', ''),
                            obj_data.get('created_at', datetime.now().isoformat()),
                            obj_data.get('completed_at')
                        )
                    )
                    
                    # Save study plan if exists
                    if 'study_plan' in obj_data:
                        plan = obj_data['study_plan']
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO study_plans
                            (plan_id, objective_id, topics, learning_path, estimated_time, prerequisites, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                f"{obj_id}_plan",
                                obj_id,
                                json.dumps(plan.get('topics', [])),
                                json.dumps(plan.get('learning_path', [])),
                                json.dumps(plan.get('estimated_time', {})),
                                json.dumps(plan.get('prerequisites', {})),
                                plan.get('created_at', datetime.now().isoformat()),
                                datetime.now().isoformat()
                            )
                        )
                    
                    # Save topic progress
                    if 'topic_progress' in obj_data:
                        for topic, progress in obj_data['topic_progress'].items():
                            progress_id = f"{user_id}_{obj_id}_{topic}"
                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO topic_progress
                                (progress_id, user_id, objective_id, topic, mastery_level, completed, last_studied)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    progress_id,
                                    user_id,
                                    obj_id,
                                    topic,
                                    progress.get('mastery_level', 0.0),
                                    progress.get('completed', False),
                                    progress.get('last_studied', datetime.now().isoformat())
                                )
                            )
                    
                    # Save quizzes and results
                    if 'quizzes' in obj_data:
                        for quiz_id, quiz_data in obj_data['quizzes'].items():
                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO quizzes
                                (quiz_id, user_id, objective_id, topic, questions, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    quiz_id,
                                    user_id,
                                    obj_id,
                                    quiz_data.get('topic', ''),
                                    json.dumps(quiz_data.get('questions', [])),
                                    quiz_data.get('created_at', datetime.now().isoformat())
                                )
                            )
                            
                            # Save quiz results if they exist
                            if 'results' in quiz_data:
                                result = quiz_data['results']
                                cursor.execute(
                                    """
                                    INSERT OR REPLACE INTO quiz_results
                                    (result_id, quiz_id, user_id, answers, score, feedback, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        f"{quiz_id}_result",
                                        quiz_id,
                                        user_id,
                                        json.dumps(result.get('answers', {})),
                                        result.get('score', 0.0),
                                        json.dumps(result.get('feedback', {})),
                                        result.get('created_at', datetime.now().isoformat())
                                    )
                                )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error saving user progress to SQLite: {e}")
            return False
    
    def load_user_progress(self, user_id: str) -> Dict[str, Any]:
        """
        Load user progress data from storage
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Dictionary containing user progress data, or empty dict if not found
        """
        if self.use_sqlite:
            return self._load_from_sqlite(user_id)
        else:
            return self._load_from_json(user_id)
    
    def _load_from_json(self, user_id: str) -> Dict[str, Any]:
        """Load data from JSON file"""
        file_path = self._get_user_json_path(user_id)
        
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading user progress from JSON: {e}")
            return {}
    
    def _load_from_sqlite(self, user_id: str) -> Dict[str, Any]:
        """Load data from SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return {}
            
            result = {
                'user_id': user_id,
                'created_at': user['created_at'],
                'learning_objectives': {}
            }
            
            # Get learning objectives
            cursor.execute(
                "SELECT * FROM learning_objectives WHERE user_id = ?", 
                (user_id,)
            )
            objectives = cursor.fetchall()
            
            for obj in objectives:
                obj_id = obj['objective_id']
                obj_data = {
                    'title': obj['title'],
                    'description': obj['description'],
                    'created_at': obj['created_at'],
                    'completed_at': obj['completed_at'],
                    'topic_progress': {},
                    'quizzes': {}
                }
                
                # Get study plan
                cursor.execute(
                    "SELECT * FROM study_plans WHERE objective_id = ?",
                    (obj_id,)
                )
                plan = cursor.fetchone()
                
                if plan:
                    obj_data['study_plan'] = {
                        'topics': json.loads(plan['topics']),
                        'learning_path': json.loads(plan['learning_path']),
                        'estimated_time': json.loads(plan['estimated_time']),
                        'prerequisites': json.loads(plan['prerequisites']),
                        'created_at': plan['created_at'],
                        'updated_at': plan['updated_at']
                    }
                
                # Get topic progress
                cursor.execute(
                    "SELECT * FROM topic_progress WHERE user_id = ? AND objective_id = ?",
                    (user_id, obj_id)
                )
                topics = cursor.fetchall()
                
                for topic in topics:
                    obj_data['topic_progress'][topic['topic']] = {
                        'mastery_level': topic['mastery_level'],
                        'completed': bool(topic['completed']),
                        'last_studied': topic['last_studied']
                    }
                
                # Get quizzes and results
                cursor.execute(
                    "SELECT * FROM quizzes WHERE user_id = ? AND objective_id = ?",
                    (user_id, obj_id)
                )
                quizzes = cursor.fetchall()
                
                for quiz in quizzes:
                    quiz_id = quiz['quiz_id']
                    quiz_data = {
                        'topic': quiz['topic'],
                        'questions': json.loads(quiz['questions']),
                        'created_at': quiz['created_at']
                    }
                    
                    # Get quiz results
                    cursor.execute(
                        "SELECT * FROM quiz_results WHERE quiz_id = ?",
                        (quiz_id,)
                    )
                    result_row = cursor.fetchone()
                    
                    if result_row:
                        quiz_data['results'] = {
                            'answers': json.loads(result_row['answers']),
                            'score': result_row['score'],
                            'feedback': json.loads(result_row['feedback']),
                            'created_at': result_row['created_at']
                        }
                    
                    obj_data['quizzes'][quiz_id] = quiz_data
                
                result['learning_objectives'][obj_id] = obj_data
            
            conn.close()
            return result
            
        except Exception as e:
            print(f"Error loading user progress from SQLite: {e}")
            return {}

    def save_study_plan(self, user_id: str, objective_id: str, study_plan: Dict[str, Any]) -> bool:
        """
        Save just the study plan for a user and learning objective
        
        Args:
            user_id: Unique identifier for the user
            objective_id: Identifier for the learning objective
            study_plan: Study plan data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing data
            data = self.load_user_progress(user_id)
            
            # Initialize if needed
            if 'learning_objectives' not in data:
                data['learning_objectives'] = {}
            
            if objective_id not in data['learning_objectives']:
                data['learning_objectives'][objective_id] = {
                    'title': study_plan.get('title', 'Unnamed Objective'),
                    'created_at': datetime.now().isoformat()
                }
            
            # Update study plan
            data['learning_objectives'][objective_id]['study_plan'] = {
                **study_plan,
                'updated_at': datetime.now().isoformat()
            }
            
            # Save back to storage
            return self.save_user_progress(user_id, data)
            
        except Exception as e:
            print(f"Error saving study plan: {e}")
            return False
    
    def update_topic_mastery(self, user_id: str, objective_id: str, 
                           topic: str, mastery_level: float, 
                           completed: bool = False) -> bool:
        """
        Update mastery level for a specific topic
        
        Args:
            user_id: Unique identifier for the user
            objective_id: Identifier for the learning objective
            topic: The topic name
            mastery_level: Mastery level (0.0 to 1.0)
            completed: Whether the topic is marked as completed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing data
            data = self.load_user_progress(user_id)
            
            # Initialize if needed
            if 'learning_objectives' not in data:
                data['learning_objectives'] = {}
            
            if objective_id not in data['learning_objectives']:
                return False
            
            if 'topic_progress' not in data['learning_objectives'][objective_id]:
                data['learning_objectives'][objective_id]['topic_progress'] = {}
            
            # Update the topic mastery
            data['learning_objectives'][objective_id]['topic_progress'][topic] = {
                'mastery_level': mastery_level,
                'completed': completed,
                'last_studied': datetime.now().isoformat()
            }
            
            # Save back to storage
            return self.save_user_progress(user_id, data)
            
        except Exception as e:
            print(f"Error updating topic mastery: {e}")
            return False
    
    def save_quiz_results(self, user_id: str, objective_id: str, 
                         quiz_id: str, topic: str, quiz_data: Dict[str, Any],
                         answers: Dict[str, Any], score: float, 
                         feedback: Dict[str, Any]) -> bool:
        """
        Save quiz results for a user
        
        Args:
            user_id: Unique identifier for the user
            objective_id: Identifier for the learning objective
            quiz_id: Unique identifier for the quiz
            topic: The topic of the quiz
            quiz_data: Quiz questions and metadata
            answers: User's answers to the quiz
            score: Score achieved (0.0 to 1.0)
            feedback: Feedback on each answer
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing data
            data = self.load_user_progress(user_id)
            
            # Initialize if needed
            if 'learning_objectives' not in data:
                data['learning_objectives'] = {}
            
            if objective_id not in data['learning_objectives']:
                return False
            
            if 'quizzes' not in data['learning_objectives'][objective_id]:
                data['learning_objectives'][objective_id]['quizzes'] = {}
            
            # Save the quiz
            timestamp = datetime.now().isoformat()
            data['learning_objectives'][objective_id]['quizzes'][quiz_id] = {
                'topic': topic,
                'questions': quiz_data,
                'created_at': timestamp,
                'results': {
                    'answers': answers,
                    'score': score,
                    'feedback': feedback,
                    'created_at': timestamp
                }
            }
            
            # Save back to storage
            return self.save_user_progress(user_id, data)
            
        except Exception as e:
            print(f"Error saving quiz results: {e}")
            return False
    
    def get_user_learning_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get a summary of all learning history for a user
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            List of all learning objectives with summary data
        """
        try:
            data = self.load_user_progress(user_id)
            
            if not data or 'learning_objectives' not in data:
                return []
            
            history = []
            
            for obj_id, obj_data in data['learning_objectives'].items():
                # Calculate overall progress
                topic_progress = obj_data.get('topic_progress', {})
                total_topics = len(topic_progress)
                completed_topics = sum(1 for t in topic_progress.values() if t.get('completed', False))
                avg_mastery = 0.0
                
                if total_topics > 0:
                    avg_mastery = sum(t.get('mastery_level', 0.0) for t in topic_progress.values()) / total_topics
                
                # Get quiz summary
                quizzes = obj_data.get('quizzes', {})
                quiz_count = len(quizzes)
                avg_score = 0.0
                
                if quiz_count > 0:
                    scores = [q.get('results', {}).get('score', 0.0) for q in quizzes.values() 
                             if 'results' in q]
                    if scores:
                        avg_score = sum(scores) / len(scores)
                
                # Create summary
                history.append({
                    'objective_id': obj_id,
                    'title': obj_data.get('title', 'Unnamed Objective'),
                    'created_at': obj_data.get('created_at'),
                    'completed_at': obj_data.get('completed_at'),
                    'total_topics': total_topics,
                    'completed_topics': completed_topics,
                    'average_mastery': avg_mastery,
                    'quiz_count': quiz_count,
                    'average_quiz_score': avg_score
                })
            
            return history
            
        except Exception as e:
            print(f"Error getting user learning history: {e}")
            return [] 