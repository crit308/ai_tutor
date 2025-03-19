"""
AI Tutor System

A system that uses OpenAI agents and file search to create a personalized learning experience.
"""

# Import the main tutor system
from .tutor_system import TutorSystem

# Import agent models for type hints
from .agents import StudyPlan, Quiz, QuizResults

# Import the storage module
from .tools.storage import UserProgressStore

# Make these available at the package level
__all__ = ['TutorSystem', 'StudyPlan', 'Quiz', 'QuizResults', 'UserProgressStore'] 