from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import os
import uuid
import json
import time
from datetime import datetime
from pathlib import Path

from ai_tutor.agents import StudyPlan, Quiz, QuizResults
from ai_tutor.tools.storage import UserProgressStore

@dataclass
class TutorContext:
    """
    Context object for the AI tutor system, used to manage user state across agents.
    This provides a central place to store and access user progress and learning data.
    """
    # User identification
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Learning state
    learning_objective: Optional[str] = None
    study_plan: Optional[StudyPlan] = None
    current_topic: Optional[str] = None
    vector_store_id: Optional[str] = None
    
    # Progress tracking
    mastery_levels: Dict[str, float] = field(default_factory=dict)
    completed_topics: List[str] = field(default_factory=list)
    
    # Quiz state
    current_quiz: Optional[Quiz] = None
    current_user_answers: Optional[Dict[int, str]] = None
    quiz_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Session data
    learning_session: Dict[str, Any] = field(default_factory=dict)
    objective_id: Optional[str] = None
    
    # Storage configuration
    storage_dir: Optional[str] = None
    use_sqlite: bool = False
    
    # Internal storage - initialized in post_init
    _progress_store: Optional[UserProgressStore] = None
    
    def __post_init__(self):
        """Initialize the progress store if not already done"""
        if self._progress_store is None:
            self._progress_store = UserProgressStore(
                storage_dir=self.storage_dir,
                use_sqlite=self.use_sqlite
            )
        
        # Generate an objective ID if not present
        if self.objective_id is None and self.learning_objective:
            self.objective_id = str(uuid.uuid4())
    
    def save_progress(self) -> bool:
        """
        Save the current user progress to persistent storage
        
        Returns:
            True if successful, False otherwise
        """
        if not self._progress_store:
            return False
            
        # Generate objective ID if needed
        if not self.objective_id and self.learning_objective:
            self.objective_id = str(uuid.uuid4())
        elif not self.objective_id:
            # No learning objective yet, nothing to save
            return False
            
        # Prepare the study plan data
        study_plan_data = {}
        if self.study_plan and hasattr(self.study_plan, 'topics'):
            study_plan_data = {
                'topics': self.study_plan.topics,
                'learning_path': self.study_plan.learning_path,
                'estimated_time': self.study_plan.estimated_time,
                'prerequisites': self.study_plan.prerequisites
            }
        
        # Prepare topic progress data
        topic_progress = {}
        topics = self.study_plan.topics if self.study_plan and hasattr(self.study_plan, 'topics') else []
        for topic in topics:
            completed = topic in self.completed_topics
            mastery_level = self.mastery_levels.get(topic, 0.0)
            topic_progress[topic] = {
                'mastery_level': mastery_level,
                'completed': completed
            }
        
        # Prepare quiz data
        quizzes = {}
        for topic, result in self.quiz_results.items():
            quiz = result.get('quiz')
            user_answers = result.get('user_answers', {})
            
            if not quiz:
                continue
                
            quiz_id = f"{self.user_id}_{topic}_quiz"
            
            quiz_data = {
                'topic': topic,
                'questions': quiz.questions if hasattr(quiz, 'questions') else [],
                'results': {
                    'answers': user_answers
                }
            }
            
            # Add score if available
            if topic in self.mastery_levels:
                quiz_data['results']['score'] = self.mastery_levels[topic]
            
            quizzes[quiz_id] = quiz_data
        
        # Create the user data structure
        user_data = {
            'learning_objectives': {
                self.objective_id: {
                    'title': self.learning_objective,
                    'description': self.learning_objective,
                    'created_at': time.strftime("%Y-%m-%dT%H:%M:%S"),
                    'study_plan': study_plan_data,
                    'topic_progress': topic_progress,
                    'quizzes': quizzes
                }
            }
        }
        
        # Save to storage
        return self._progress_store.save_user_progress(self.user_id, user_data)
    
    def load_progress(self) -> bool:
        """
        Load user progress from persistent storage
        
        Returns:
            True if data was loaded successfully, False otherwise
        """
        if not self._progress_store:
            return False
            
        try:
            user_data = self._progress_store.load_user_progress(self.user_id)
            
            if not user_data or not user_data.get('learning_objectives'):
                return False
                
            # Find the most recent learning objective
            learning_objectives = user_data.get('learning_objectives', {})
            if not learning_objectives:
                return False
                
            # Sort by created_at date and get the most recent
            sorted_objectives = sorted(
                learning_objectives.items(),
                key=lambda x: x[1].get('created_at', ''),
                reverse=True
            )
            
            if not sorted_objectives:
                return False
                
            obj_id, obj_data = sorted_objectives[0]
            
            # Store the objective ID
            self.objective_id = obj_id
            
            # Load the learning objective
            self.learning_objective = obj_data.get('title', '')
            
            # Load the study plan if available
            if 'study_plan' in obj_data:
                plan = obj_data['study_plan']
                # Verify that all required fields are present
                required_fields = ['topics', 'learning_path', 'estimated_time', 'prerequisites']
                if all(field in plan for field in required_fields):
                    self.study_plan = StudyPlan(
                        topics=plan.get('topics', []),
                        learning_path=plan.get('learning_path', []),
                        estimated_time=plan.get('estimated_time', {}),
                        prerequisites=plan.get('prerequisites', {})
                    )
                else:
                    return False
            
            # Load mastery levels
            if 'topic_progress' in obj_data:
                for topic, progress in obj_data['topic_progress'].items():
                    self.mastery_levels[topic] = progress.get('mastery_level', 0.0)
                    if progress.get('completed', False):
                        self.completed_topics.append(topic)
            
            # Load quiz results
            if 'quizzes' in obj_data:
                for quiz_id, quiz_data in obj_data['quizzes'].items():
                    topic = quiz_data.get('topic', '')
                    if topic and 'results' in quiz_data:
                        self.quiz_results[topic] = {
                            'quiz': Quiz(
                                topic=topic,
                                questions=quiz_data.get('questions', []),
                                time_limit=quiz_data.get('time_limit', '10 minutes')
                            ),
                            'user_answers': quiz_data.get('results', {}).get('answers', {})
                        }
            
            return True
        except Exception as e:
            print(f"Error loading user progress: {e}")
            return False
    
    def create_default_study_plan(self):
        """
        Create a default study plan when one can't be created or loaded
        """
        default_topics = ["Introduction", "Key Concepts", "Applications", "Advanced Topics"]
        self.study_plan = StudyPlan(
            topics=default_topics,
            learning_path=default_topics,
            estimated_time={topic: "30 minutes" for topic in default_topics},
            prerequisites={}
        )
        return self.study_plan
    
    def store_quiz_answers(self, quiz: Quiz, user_answers: Dict[int, str]):
        """
        Store quiz and user answers
        
        Args:
            quiz: The quiz that was administered
            user_answers: The user's answers to the quiz
        """
        self.current_quiz = quiz
        self.current_user_answers = user_answers
        topic = quiz.topic if hasattr(quiz, 'topic') else self.current_topic
        self.current_topic = topic
        
        if topic:
            self.quiz_results[topic] = {
                "quiz": quiz,
                "user_answers": user_answers
            }
        
        # Update session data
        self.learning_session["quiz_results"] = self.quiz_results
        
        # Save to persistent storage
        self.save_progress()
    
    def update_mastery_level(self, topic: str, mastery_level: float, completed: bool = False):
        """
        Update the mastery level for a topic
        
        Args:
            topic: The topic to update
            mastery_level: The new mastery level (0.0 to 1.0)
            completed: Whether the topic is now completed
        """
        self.mastery_levels[topic] = mastery_level
        
        if completed and topic not in self.completed_topics:
            self.completed_topics.append(topic)
        
        # Save to persistent storage
        self.save_progress()
    
    def mark_learning_complete(self):
        """
        Mark the current learning objective as complete
        """
        if not self.objective_id or not self._progress_store:
            return
            
        # Load data, update completion timestamp, and save back
        user_data = self._progress_store.load_user_progress(self.user_id)
        if user_data and 'learning_objectives' in user_data:
            if self.objective_id in user_data['learning_objectives']:
                user_data['learning_objectives'][self.objective_id]['completed_at'] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self._progress_store.save_user_progress(self.user_id, user_data) 