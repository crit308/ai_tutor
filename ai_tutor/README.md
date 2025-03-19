# AI Tutor System

An adaptive learning system that uses OpenAI's Agents SDK and File Search to create a personalized learning experience.

## Overview

The AI Tutor System allows users to:

1. Upload learning materials (PDF, docx, text, etc.)
2. Define their learning objectives
3. Receive a customized study plan
4. Get interactive lessons on each topic
5. Take quizzes to test understanding
6. Receive personalized feedback and progress tracking
7. Adapt the learning path based on performance

## Architecture

The system uses a multi-agent approach with specialized agents:

- **Planner Agent**: Analyzes materials and creates a structured study plan
- **Teacher Agent**: Delivers clear, engaging lessons on each topic
- **Quiz Creator Agent**: Designs effective assessments to test understanding
- **Quiz Evaluator Agent**: Analyzes responses and provides feedback
- **Progress Agent**: Tracks mastery and adapts the learning path

## Requirements

- Python 3.8+
- OpenAI API key
- Required packages: `openai`, `agents`

## Setup

1. Ensure you have the OpenAI Agents SDK installed:
   ```
   pip install openai-agents
   ```

2. Set your OpenAI API key as an environment variable:
   ```
   export OPENAI_API_KEY=your_api_key  # On Linux/Mac
   set OPENAI_API_KEY=your_api_key     # On Windows
   ```

3. Run the tutor system:
   ```
   python -m ai_tutor.main
   ```

## Usage

1. Start the AI Tutor
2. Upload learning materials (URLs or file paths)
3. Enter your learning objective
4. Review the generated study plan
5. Begin the learning journey through each topic
6. Take quizzes to test understanding
7. Complete the entire learning path

## Features

- **Document Understanding**: Uses OpenAI's File Search for deep understanding of uploaded materials
- **Personalized Study Plans**: Creates custom learning paths based on content and objectives
- **Adaptive Learning**: Adjusts pace and focus based on performance
- **Interactive Lessons**: Clear, engaging explanations with examples and analogies
- **Effective Assessment**: Mix of question types to test different levels of understanding
- **Detailed Feedback**: Identifies strengths, weaknesses, and misconceptions
- **Progress Tracking**: Monitors mastery levels across all topics

## Future Enhancements

- Web interface for easier document upload and interaction
- More input modalities (video, audio, etc.)
- Collaborative learning support
- Expanded quiz types and interactive exercises
- Export and share learning progress
- Integration with existing LMS platforms 