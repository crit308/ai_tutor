#!/usr/bin/env python
"""
Run AI Tutor Web Interface

This script launches the web interface for the AI tutor system.
"""

import os
import sys

if __name__ == "__main__":
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set it using one of these methods:")
        print("  export OPENAI_API_KEY=your_api_key  # On Linux/Mac")
        print("  set OPENAI_API_KEY=your_api_key     # On Windows")
        sys.exit(1)
    
    # Import the Flask app after setting API key
    from web_interface import app
    
    # Optional arguments for host and port
    import argparse
    parser = argparse.ArgumentParser(description='Run the AI Tutor Web Interface')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to run the web interface on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the web interface on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    # Run the Flask app
    print(f"=== AI Tutor Web Interface ===")
    print(f"Starting server at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the server")
    
    app.run(host=args.host, port=args.port, debug=args.debug) 