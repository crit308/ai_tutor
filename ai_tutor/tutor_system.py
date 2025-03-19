from agents import Agent, Runner, FileSearchTool, handoff, RunConfig
from agents.result import RunResult
from agents.model_settings import ModelSettings
import asyncio
import time
import uuid
from typing import List, Dict, Any, Optional, TypeVar, Generic

# Import our custom agents
from ai_tutor.agents import (
    planner_agent, 
    teacher_agent, 
    quiz_creator_agent, 
    quiz_evaluator_agent,
    StudyPlan,
    Quiz, 
    QuizResults
)

# Import document tools
from ai_tutor.tools import (
    create_vector_store, 
    upload_file_to_store, 
    check_file_status,
    UserProgressStore,
    TutorContext,
    # User progress tools
    save_study_plan,
    save_quiz_results,
    get_user_progress,
    store_quiz_and_answers,
    mark_learning_complete
)

# Define a type variable for our context
T = TypeVar('T')

class TutorSystem(Generic[T]):
    """
    AI Tutor System that manages the learning process using specialized agents
    """
    def __init__(self, user_id: Optional[str] = None, storage_dir: Optional[str] = None, use_sqlite: bool = False):
        """
        AI Tutor System that manages the learning process using specialized agents
        
        Args:
            user_id: Unique identifier for the user. If not provided, a random UUID will be generated.
            storage_dir: Directory to store user progress data. Defaults to ~/.ai_tutor.
            use_sqlite: Whether to use SQLite instead of JSON files for storage.
        """
        # Initialize context
        self.context = TutorContext(
            user_id=user_id if user_id else str(uuid.uuid4()),
            storage_dir=storage_dir,
            use_sqlite=use_sqlite
        )
        
        # Load existing progress
        self.context.load_progress()
        
        # Create a run config for all agent runs
        self.run_config = RunConfig(
            workflow_name="ai_tutor",
            handoff_input_filter=None,  # Use default handoff behavior
            trace_include_sensitive_data=True,  # Include inputs/outputs in traces for debugging
            model="gpt-4o",  # Use a more capable model for better handoff understanding
            model_settings=ModelSettings(
                temperature=0.2,  # Lower temperature for more deterministic behavior
                tool_choice="auto",  # Let the model choose when to use tools
                parallel_tool_calls=True,  # Enable parallel tool calls
                max_tokens=4000  # Ensure enough tokens for responses
            )
        )
        
        # Set up agents with handoffs
        self._setup_agents()
    
    def _setup_agents(self):
        """
        Set up all agents with the proper handoffs
        """
        # Main agents will be properly initialized when vector store is ready
        self.planner_with_tools = None
        self.teacher_with_tools = None
        self.quiz_creator_with_tools = None
        self.quiz_evaluator_with_tools = None
    
    def _initialize_agents_with_tools(self):
        """
        Initialize all agents with tools and handoffs after vector store is ready
        """
        # Create FileSearchTool with the vector store ID
        self.file_search_tool = FileSearchTool(
            vector_store_ids=[self.context.vector_store_id],
            max_num_results=5
        )
        
        # Common tools for all agents
        common_tools = [
            self.file_search_tool,
            get_user_progress
        ]
        
        # Initialize all agents with specific tools
        self.quiz_creator_with_tools = Agent[TutorContext](
            name=quiz_creator_agent.name,
            instructions=quiz_creator_agent.instructions,
            output_type=quiz_creator_agent.output_type,
            tools=common_tools,
            handoff_description="An expert quiz creator who designs effective assessments for educational topics"
        )
        
        self.quiz_evaluator_with_tools = Agent[TutorContext](
            name=quiz_evaluator_agent.name,
            instructions=quiz_evaluator_agent.instructions,
            output_type=quiz_evaluator_agent.output_type,
            tools=common_tools + [save_quiz_results],
            handoff_description="An expert evaluator who assesses quiz responses and provides feedback"
        )
        
        self.teacher_with_tools = Agent[TutorContext](
            name=teacher_agent.name,
            instructions=teacher_agent.instructions,
            tools=common_tools,
            handoff_description="An expert teacher who explains concepts clearly and effectively"
        )
        
        self.planner_with_tools = Agent[TutorContext](
            name=planner_agent.name,
            instructions=planner_agent.instructions,
            output_type=planner_agent.output_type,
            tools=common_tools + [save_study_plan, mark_learning_complete],
            handoff_description="An educational planner who creates personalized learning pathways"
        )
        
        # Set up handoffs between agents
        # Planner -> Teacher
        handoff(
            self.planner_with_tools,
            self.teacher_with_tools,
            tool_name="transfer_to_teacher",
            tool_description="Transfer to the Teacher agent to teach a specific topic"
        )
        
        # Teacher -> Quiz Creator
        handoff(
            self.teacher_with_tools,
            self.quiz_creator_with_tools,
            tool_name="transfer_to_quiz_creator",
            tool_description="Transfer to the Quiz Creator agent to create a quiz for the topic"
        )
        
        # Quiz Creator -> Quiz Evaluator
        handoff(
            self.quiz_creator_with_tools,
            self.quiz_evaluator_with_tools,
            tool_name="transfer_to_quiz_evaluator",
            tool_description="Transfer to the Quiz Evaluator agent to evaluate quiz responses"
        )
        
        # Quiz Evaluator -> Planner
        handoff(
            self.quiz_evaluator_with_tools,
            self.planner_with_tools,
            tool_name="transfer_to_planner",
            tool_description="Transfer to the Study Planner agent to update the learning path"
        )
    
    # Convenience properties to access context data
    @property
    def user_id(self) -> str:
        return self.context.user_id
        
    @property
    def learning_objective(self) -> Optional[str]:
        return self.context.learning_objective
        
    @property
    def study_plan(self) -> Optional[StudyPlan]:
        return self.context.study_plan
        
    @property
    def mastery_levels(self) -> Dict[str, float]:
        return self.context.mastery_levels
        
    @property
    def completed_topics(self) -> List[str]:
        return self.context.completed_topics
    
    async def setup_knowledge_base(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Set up the knowledge base with the provided files
        
        Args:
            file_paths: List of file paths or URLs to add to the knowledge base
            
        Returns:
            Dictionary with vector_store_id and file_ids
        """
        # Create a new vector store
        vector_store_name = f"ai_tutor_{self.context.user_id}"
        vector_store_result = await create_vector_store(name=vector_store_name)
        vector_store_id = vector_store_result
        
        if not vector_store_id:
            raise ValueError("Failed to create vector store")
        
        # Store the vector store ID in the context
        self.context.vector_store_id = vector_store_id
        
        # Upload each file to the vector store
        file_ids = []
        for file_path in file_paths:
            upload_result = await upload_file_to_store(
                vector_store_id=vector_store_id,
                file_path=file_path
            )
            file_id = upload_result
            if file_id:
                file_ids.append(file_id)
                
                # Check that the file was uploaded successfully
                await check_file_status(
                    vector_store_id=vector_store_id,
                    file_id=file_id
                )
        
        if not file_ids:
            raise ValueError("Failed to upload any files to the vector store")
        
        # Initialize the agents with the vector store
        self._initialize_agents_with_tools()
        
        return {
            "vector_store_id": vector_store_id,
            "file_ids": file_ids
        }
    
    async def create_study_plan(self, learning_objective: str, max_turns: int = 10) -> RunResult:
        """
        Create a study plan for a specific learning objective
        
        Args:
            learning_objective: The learning objective or topic to study
            max_turns: Maximum number of turns for the agent conversation
            
        Returns:
            RunResult containing study plan and information about handoffs
        """
        # Set the learning objective in the context
        self.context.learning_objective = learning_objective
        print(f"\n=== Creating Study Plan for: {learning_objective} ===\n")
        
        # Use the study planner agent to create a study plan
        result = await Runner.run(
            self.planner_with_tools,
            input=f"""
            Create a study plan for the learning objective: {learning_objective}
            
            Use the available reference materials to identify key concepts and topics 
            that should be covered to master this subject.
            
            The study plan should include:
            - A comprehensive list of topics to learn
            - A logical learning path that orders topics from basic to advanced
            - Estimated time needed for each topic
            - Prerequisites for each topic where applicable
            
            After creating the plan, hand off to the Teacher agent to begin teaching 
            the first topic in the learning path.
            """,
            run_config=self.run_config,
            context=self.context,
            max_turns=max_turns
        )
        
        return result
    
    async def store_quiz_answers(self, quiz: Quiz, user_answers: Dict[int, str]):
        """
        Store quiz and user answers to be accessible across handoffs
        
        Args:
            quiz: The quiz that was administered
            user_answers: The user's answers to the quiz
        """
        self.context.store_quiz_answers(quiz, user_answers)
    
    async def get_user_answers(self, quiz: Quiz) -> Dict[int, str]:
        """
        Collect user answers to a quiz
        
        Args:
            quiz: The quiz to collect answers for
            
        Returns:
            Dictionary mapping question indices to user answers
        """
        print(f"\n=== Quiz on {quiz.topic} ===")
        print(f"Recommended time: {quiz.time_limit}\n")
        
        user_answers = {}
        
        for i, question in enumerate(quiz.questions):
            print(f"\nQuestion {i+1}: {question.text}")
            
            # Display multiple choice options if available
            if question.options:
                for j, option in enumerate(question.options):
                    print(f"  {chr(65+j)}. {option}")
                
                valid_responses = set(chr(65+j) for j in range(len(question.options)))
                
                # Get user input with validation
                while True:
                    response = input("\nYour answer (letter): ").strip().upper()
                    if response in valid_responses:
                        break
                    print(f"Invalid response. Please enter a letter between A-{chr(64+len(question.options))}")
                
                user_answers[i] = response
            else:
                # Free-form response
                response = input("\nYour answer: ").strip()
                user_answers[i] = response
        
        print("\nQuiz completed! Evaluating your responses...\n")
        return user_answers
    
    async def evaluate_quiz(self, quiz: Quiz, user_answers: Dict[int, str], max_turns: int = 10) -> RunResult:
        """
        Evaluate a quiz using the Quiz Evaluator agent
        
        Args:
            quiz: The quiz to evaluate
            user_answers: Dictionary mapping question indices to user answers
            max_turns: Maximum number of turns for the agent conversation
            
        Returns:
            RunResult containing QuizResults and information about handoffs
        """
        self.context.current_topic = quiz.topic
        
        print(f"\n=== Evaluating Quiz on {quiz.topic} ===\n")
        
        # Store the quiz and user answers for other agents to access
        await self.store_quiz_answers(quiz, user_answers)
        
        # Convert user answers to a format suitable for the evaluator
        answer_text = "\n".join([f"Question {i+1}: {ans}" for i, ans in user_answers.items()])
        
        # Use the quiz evaluator agent with handoffs
        result = await Runner.run(
            self.quiz_evaluator_with_tools,
            input=f"""
            Evaluate the following quiz responses for the topic: {quiz.topic}
            
            Quiz Questions:
            {quiz.questions_text}
            
            User Answers:
            {answer_text}
            
            Please evaluate each answer carefully, provide detailed feedback, calculate the score, and 
            update the student's mastery level using the save_quiz_results tool.
            
            Then hand off to the Study Planner agent to update the study plan based on these results.
            """,
            run_config=self.run_config,
            context=self.context,
            max_turns=max_turns
        )
        
        return result
    
    async def process_agent_handoff_chain(self, initial_result: RunResult, max_turns: int = 30) -> Dict[str, Any]:
        """
        Process a chain of agent handoffs starting from an initial result
        
        Args:
            initial_result: The initial RunResult from which to start the handoff chain
            max_turns: Maximum number of turns for each agent conversation
            
        Returns:
            Dictionary with results from the entire handoff chain
        """
        all_results = {
            "initial_result": initial_result,
            "handoff_results": []
        }
        
        # Process handoffs until there are no more or we find a loop
        current_result = initial_result
        agent_ids_seen = set()
        
        while current_result and current_result.handoff_info:
            # Get information about the handoff
            target_agent = current_result.handoff_info.target_agent
            target_agent_id = id(target_agent)
            
            # Check for loops in the handoff chain
            if target_agent_id in agent_ids_seen:
                print("Warning: Detected a loop in the handoff chain. Stopping.")
                break
                
            agent_ids_seen.add(target_agent_id)
            
            # Run the next agent in the chain
            next_result = await Runner.run(
                starting_agent=target_agent,
                input=current_result.handoff_info.handoff_message,
                run_config=self.run_config,
                context=self.context,
                max_turns=max_turns
            )
            
            # Add this result to our collection
            all_results["handoff_results"].append(next_result)
            
            # Continue the chain
            current_result = next_result
        
        return all_results
    
    async def complete_learning_objective(self, max_turns: int = 30) -> Dict[str, Any]:
        """
        Run the complete learning process for the learning objective using agent handoffs
        
        Args:
            max_turns: Maximum number of turns for the agent conversation
            
        Returns:
            Final learning results and progress
        """
        if not self.context.learning_objective:
            raise ValueError("Learning objective not set. Call create_study_plan first.")
        
        if not self.context.study_plan:
            print("Warning: Study plan not found. Creating a default study plan.")
            self.context.create_default_study_plan()
        
        # Validate the study plan
        if not hasattr(self.context.study_plan, 'topics') or not self.context.study_plan.topics:
            print("Warning: Study plan is invalid. Creating a default study plan.")
            self.context.create_default_study_plan()
            
        if not hasattr(self.context.study_plan, 'learning_path') or not self.context.study_plan.learning_path:
            # Set learning path to topics if missing
            self.context.study_plan.learning_path = self.context.study_plan.topics
        
        print(f"\n=== Starting Learning Process for: {self.context.learning_objective} ===\n")
        
        # Initialize the learning session
        self.context.learning_session = {
            "learning_objective": self.context.learning_objective,
            "initial_plan": self.context.study_plan,
            "topics_covered": [],
            "quiz_results": {}
        }
        
        # Start the learning loop with the Study Planner
        # The handoffs will manage the flow from here:
        # Study Planner -> Teacher -> Quiz Creator -> Quiz Evaluator -> Study Planner -> ...
        first_topic = self.context.study_plan.learning_path[0] if self.context.study_plan.learning_path else "Introduction"
        
        initial_result = await Runner.run(
            self.planner_with_tools,
            input=f"""
            You are starting a new learning session for: {self.context.learning_objective}.
            
            Study Plan:
            - Topics: {', '.join(self.context.study_plan.topics)}
            - Learning Path: {', '.join(self.context.study_plan.learning_path)}
            - Estimated Time: {self.context.study_plan.estimated_time}
            
            Begin by handing off to the Teacher agent to teach the first topic in the learning path: {first_topic}.
            In your handoff, explicitly specify that the Teacher should teach the topic: "{first_topic}".
            """,
            run_config=self.run_config,
            context=self.context,
            max_turns=max_turns
        )
        
        # Process the handoff chain
        all_results = await self.process_agent_handoff_chain(initial_result, max_turns)
        
        # Check if learning is complete
        learning_complete = "LEARNING_COMPLETE" in str(all_results)
        if learning_complete:
            print("\n=== Learning Objective Completed! ===")
            self.context.mark_learning_complete()
            
        return {
            "learning_objective": self.context.learning_objective,
            "session_details": self.context.learning_session,
            "final_results": all_results,
            "completed": learning_complete
        } 