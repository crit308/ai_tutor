import asyncio
import os
import sys
from .tutor_system import TutorSystem

async def main():
    # Check if OpenAI API key is set
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set your OpenAI API key using:")
        print("  export OPENAI_API_KEY=your_api_key  # On Linux/Mac")
        print("  set OPENAI_API_KEY=your_api_key     # On Windows")
        return

    print("=== AI Tutor System ===")
    print("This system helps you learn any topic by uploading learning materials.")
    
    # Initialize the tutor system
    tutor = TutorSystem()
    
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
    await tutor.setup_knowledge_base(file_paths)
    
    # Get the learning objective
    learning_objective = input("\nWhat would you like to learn about? ")
    
    # Create a study plan
    study_plan = await tutor.create_study_plan(learning_objective)
    
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
        print(f"You've completed your learning objective: {learning_objective}")
        
        # Show final mastery levels
        if tutor.mastery_levels:
            print("\nFinal mastery levels:")
            for topic, level in tutor.mastery_levels.items():
                print(f"  - {topic}: {level*100:.1f}%")
    else:
        print("\nExiting. You can run the program again when you're ready to learn.")

if __name__ == "__main__":
    asyncio.run(main()) 