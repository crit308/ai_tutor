# AI Tutor Persistent Storage System

This module provides a persistent storage system for the AI Tutor, enabling it to track user progress across learning sessions.

## Features

- Persistent storage of user learning progress
- Support for both JSON file and SQLite database backends
- Tracking of study plans, topic mastery levels, quiz results, and learning history
- Ability to resume learning sessions from where the user left off

## Usage

The UserProgressStore class provides methods to save and load user progress data:

```python
from ai_tutor.tools import UserProgressStore

# Initialize with default storage location (uses JSON files by default)
progress_store = UserProgressStore()

# Or use SQLite with a custom storage directory
progress_store = UserProgressStore(storage_dir="/path/to/data", use_sqlite=True)

# Save user progress
progress_store.save_user_progress("user123", data)

# Load user progress
user_data = progress_store.load_user_progress("user123")

# Get a summary of learning history
history = progress_store.get_user_learning_history("user123")
```

## Data Structure

The storage system organizes data hierarchically:

- Users
  - Learning Objectives
    - Study Plans
    - Topic Progress
    - Quizzes and Results

This structure allows for multiple users and learning objectives to be tracked independently.

## Command-line Usage

You can use the persistent storage system with the AI Tutor by providing command-line arguments:

```bash
python run_tutor.py --user-id user123 --storage-dir /path/to/data --use-sqlite
```

These arguments:
- `--user-id`: Specify a unique user ID for progress tracking
- `--storage-dir`: Set a custom directory for storing progress data
- `--use-sqlite`: Use SQLite database instead of JSON files

## Integration with AI Tutor

The storage system is integrated into the TutorSystem class, which automatically:

1. Loads existing user progress when initialized
2. Saves study plans after creation
3. Tracks topic mastery levels
4. Records quiz results
5. Saves the final learning state when a learning objective is completed 