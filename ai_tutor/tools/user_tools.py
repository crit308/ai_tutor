from typing import Dict, List, Optional, Any
from agents import function_tool, RunContextWrapper

from ai_tutor.tools.context import TutorContext
from ai_tutor.agents import StudyPlan, Quiz, QuizResults

@function_tool
async def save_study_plan(
    wrapper: RunContextWrapper[TutorContext],
    learning_objective: str,
    topics: List[str],
    learning_path: List[str],
    estimated_time: Dict[str, str],
    prerequisites: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Save a study plan for the current learning objective.
    
    Args:
        learning_objective: The learning objective
        topics: List of topics to cover
        learning_path: Ordered sequence of topics to learn
        estimated_time: Dictionary mapping topics to time estimates
        prerequisites: Optional dictionary mapping topics to prerequisite topics
        
    Returns:
        A confirmation message
    """
    context = wrapper.context
    context.learning_objective = learning_objective
    
    # Create the StudyPlan object
    context.study_plan = StudyPlan(
        topics=topics,
        learning_path=learning_path,
        estimated_time=estimated_time,
        prerequisites=prerequisites or {}
    )
    
    # Save to persistent storage
    success = context.save_progress()
    
    if success:
        return f"Study plan for '{learning_objective}' saved successfully with {len(topics)} topics."
    else:
        return "Failed to save study plan. Please try again."

@function_tool
async def save_quiz_results(
    wrapper: RunContextWrapper[TutorContext],
    topic: str,
    score: float,
    feedback: List[str]
) -> str:
    """
    Save quiz results and update mastery level for a topic.
    
    Args:
        topic: The topic of the quiz
        score: The score achieved (0.0 to 1.0)
        feedback: List of feedback items for each question
        
    Returns:
        A confirmation message
    """
    context = wrapper.context
    
    # Update mastery level
    completed = score >= 0.7  # Mark as completed if score is high enough
    context.update_mastery_level(topic, score, completed)
    
    return f"Quiz results for '{topic}' saved. Mastery level: {score:.1%}, Completed: {completed}"

@function_tool
async def get_user_progress(
    wrapper: RunContextWrapper[TutorContext]
) -> Dict[str, Any]:
    """
    Get the current user's learning progress.
    
    Returns:
        A dictionary containing user progress data
    """
    context = wrapper.context
    
    result = {
        "learning_objective": context.learning_objective,
        "topics": context.study_plan.topics if context.study_plan and hasattr(context.study_plan, 'topics') else [],
        "mastery_levels": context.mastery_levels,
        "completed_topics": context.completed_topics,
        "total_topics": len(context.study_plan.topics) if context.study_plan and hasattr(context.study_plan, 'topics') else 0
    }
    
    # Calculate overall progress
    if result["total_topics"] > 0:
        result["completion_percentage"] = len(result["completed_topics"]) / result["total_topics"] * 100
        
        # Calculate average mastery
        if context.mastery_levels:
            result["average_mastery"] = sum(context.mastery_levels.values()) / len(context.mastery_levels)
        else:
            result["average_mastery"] = 0.0
    else:
        result["completion_percentage"] = 0.0
        result["average_mastery"] = 0.0
    
    return result

@function_tool
async def store_quiz_and_answers(
    wrapper: RunContextWrapper[TutorContext],
    quiz_topic: str,
    questions: List[Dict[str, Any]],
    user_answers: Dict[str, str]
) -> str:
    """
    Store a quiz and the user's answers.
    
    Args:
        quiz_topic: The topic of the quiz
        questions: List of question objects
        user_answers: Dictionary mapping question indices to user answers
        
    Returns:
        A confirmation message
    """
    context = wrapper.context
    
    # Create a Quiz object
    quiz = Quiz(
        topic=quiz_topic,
        questions=questions,
        time_limit="10 minutes"  # Default time limit
    )
    
    # Convert answer keys to integers
    int_answers = {int(k): v for k, v in user_answers.items()}
    
    # Store the quiz and answers
    context.store_quiz_answers(quiz, int_answers)
    
    return f"Quiz on '{quiz_topic}' with {len(questions)} questions and user answers stored successfully."

@function_tool
async def mark_learning_complete(
    wrapper: RunContextWrapper[TutorContext]
) -> str:
    """
    Mark the current learning objective as complete.
    
    Returns:
        A confirmation message
    """
    context = wrapper.context
    context.mark_learning_complete()
    
    return f"Learning objective '{context.learning_objective}' marked as complete." 