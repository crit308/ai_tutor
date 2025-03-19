#!/usr/bin/env python
"""
AI Tutor System Runner

This script launches the AI tutor system.
"""

import asyncio
import os
import sys
import argparse
from ai_tutor.tutor_system import TutorSystem
from ai_tutor.tools import TutorContext
from agents.result import RunResult
from agents.items import HandoffOutputItem
from ai_tutor.agents import QuizResults, ProgressUpdate, StudyPlan

def print_agent_tools(agent, level=0):
    """
    Print the tools available to an agent, including handoffs, for debugging purposes
    """
    indent = "  " * level
    print(f"{indent}Agent: {agent.name}")
    
    print(f"{indent}Tools:")
    for tool in agent.tools:
        print(f"{indent}  - {tool.name}: {getattr(tool, 'description', 'No description')}")
    
    print(f"{indent}Handoffs:")
    for handoff_obj in agent.handoffs:
        # Get the agent name instead of trying to access target_agent or agent
        agent_name = getattr(handoff_obj, "agent_name", None)
        if agent_name:
            # This is a Handoff object
            tool_name = getattr(handoff_obj, "tool_name", None) or f"transfer_to_{agent_name.lower().replace(' ', '_')}"
            tool_desc = getattr(handoff_obj, "tool_description", None) or f"Transfer to {agent_name}"
            print(f"{indent}  - {tool_name}: {tool_desc}")
            
            # We can't recursively print tools since we don't have direct access to the agent
            # Uncomment this if you find a way to get the agent from the handoff
            # print_agent_tools(handoff_agent, level + 2)
        else:
            # This might be a direct Agent object in the handoffs list
            target_name = getattr(handoff_obj, "name", "Unknown Agent")
            print(f"{indent}  - transfer_to_{target_name.lower().replace(' ', '_')}: Transfer to {target_name}")
            print_agent_tools(handoff_obj, level + 2)

async def run_tutor():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run the AI Tutor System')
    parser.add_argument('--user-id', type=str, help='User ID for progress tracking')
    parser.add_argument('--storage-dir', type=str, help='Directory to store user progress data')
    parser.add_argument('--use-sqlite', action='store_true', help='Use SQLite database for storage')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    # Check if OpenAI API key is set
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set your OpenAI API key using:")
        print("  export OPENAI_API_KEY=your_api_key  # On Linux/Mac")
        print("  set OPENAI_API_KEY=your_api_key     # On Windows")
        return

    print("=== AI Tutor System ===")
    print("This system helps you learn any topic by uploading learning materials.")
    
    # Initialize the tutor system with user ID if provided
    tutor = TutorSystem[TutorContext](
        user_id=args.user_id,
        storage_dir=args.storage_dir,
        use_sqlite=args.use_sqlite
    )
    
    # Print user info if available
    if args.user_id:
        print(f"\nWelcome back, user {args.user_id}!")
        # If user has existing learning objective, ask if they want to continue
        if tutor.learning_objective:
            print(f"\nYou have an existing learning objective: {tutor.learning_objective}")
            continue_learning = input("Would you like to continue with this objective? (y/n): ")
            if continue_learning.lower() == 'y':
                # Skip to the learn section
                start_learning = 'y'
                learning_objective = tutor.learning_objective
                study_plan = tutor.study_plan
                
                # Display the study plan
                if study_plan and hasattr(study_plan, 'topics'):
                    print("\n=== Your Study Plan ===")
                    print(f"Topics to cover: {', '.join(study_plan.topics)}")
                    print(f"Learning path: {', '.join(study_plan.learning_path)}")
                    print("\nEstimated time for each topic:")
                    for topic, time in study_plan.estimated_time.items():
                        print(f"  - {topic}: {time}")
                else:
                    print("\nNo valid study plan found. You'll create a new one.")
                
                # Display progress
                if tutor.mastery_levels:
                    print("\nYour progress so far:")
                    for topic, level in tutor.mastery_levels.items():
                        print(f"  - {topic}: {level*100:.1f}%")
                
                if tutor.completed_topics:
                    print("\nCompleted topics:")
                    for topic in tutor.completed_topics:
                        print(f"  - {topic}")
                        
                # Jump to learning section
                goto_learning = True
            else:
                goto_learning = False
        else:
            goto_learning = False
    else:
        goto_learning = False
    
    # If not continuing previous session, set up a new one
    if not goto_learning:
        # In a real application, you would have a UI for uploading files
        # For demonstration, we'll use a predefined list of files or URLs
        
        sample_files = [
            "https://cdn.openai.com/API/docs/deep_research_blog.pdf"
        ]
        
        custom_files = input("\nEnter URLs or file paths to learning materials (comma-separated), or press Enter to use sample file: ")
        
        if custom_files.strip():
            file_paths = [path.strip() for path in custom_files.split(",")]
        else:
            print("\nUsing sample file for demonstration.")
            file_paths = sample_files
        
        # Setup knowledge base with the documents
        print("\nSetting up knowledge base with the provided documents...")
        knowledge_base_result = await tutor.setup_knowledge_base(file_paths)
        
        if not knowledge_base_result.get("file_ids"):
            print("Error: Failed to upload files to the knowledge base.")
            return
            
        print(f"Successfully uploaded {len(knowledge_base_result['file_ids'])} files to the knowledge base.")
        
        # Get the learning objective
        learning_objective = input("\nWhat would you like to learn about? ")
        
        # Create a study plan
        study_plan_result = await tutor.create_study_plan(learning_objective)
        
        # Get the actual study plan from the tutor instance
        study_plan = tutor.study_plan
        
        # Check if study plan was created successfully
        if not study_plan or not hasattr(study_plan, 'topics'):
            print("\nWarning: Failed to create a proper study plan. Using a default study plan instead.")
            # Create a default plan for display
            default_topics = ["Introduction", "Key Concepts", "Applications", "Advanced Topics"]
            default_time = {topic: "30 minutes" for topic in default_topics}
            
            # Display a simple study plan
            print("\n=== Your Study Plan ===")
            print(f"Topics to cover: {', '.join(default_topics)}")
            print(f"Learning path: {', '.join(default_topics)}")
            print("\nEstimated time for each topic:")
            for topic, time in default_time.items():
                print(f"  - {topic}: {time}")
        else:
            # Display the study plan
            print("\n=== Your Study Plan ===")
            print(f"Topics to cover: {', '.join(study_plan.topics)}")
            print(f"Learning path: {', '.join(study_plan.learning_path)}")
            print("\nEstimated time for each topic:")
            for topic, time in study_plan.estimated_time.items():
                print(f"  - {topic}: {time}")
        
        # Ask if the user wants to start learning
        start_learning = input("\nReady to start learning? (y/n): ")
    
    if start_learning.lower() == 'y':
        # Start the learning process with agent handoffs
        print("\n=== Starting Learning Process ===")
        print("The system will guide you through the topics using specialized AI agents.\n")
        
        # Run the complete learning process
        # All steps (teaching, quiz creation, evaluation, progress tracking) 
        # will be handled through agent handoffs
        results = await tutor.complete_learning_objective()
        
        # Print final results
        print("\n=== Learning Complete! ===")
        print(f"You've completed your learning objective: {tutor.learning_objective}")
        
        # Show final mastery levels
        if tutor.mastery_levels:
            print("\nFinal mastery levels:")
            for topic, level in tutor.mastery_levels.items():
                print(f"  - {topic}: {level*100:.1f}%")
                
        # Show completion status
        if results.get("completed", False):
            print("\nCongratulations! You have successfully completed this learning objective.")
            print("Your progress has been saved.")
        else:
            print("\nYou've made progress on this learning objective.")
            print("Your progress has been saved and you can continue later.")
            
    else:
        print("\nExiting. You can run the program again when you're ready to learn.")

if __name__ == "__main__":
    asyncio.run(run_tutor()) 