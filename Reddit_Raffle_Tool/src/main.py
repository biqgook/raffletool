"""
Reddit Raffle Tool - Main Application Entry Point

A Python GUI application for parsing Reddit posts and managing user information
for raffles and giveaways.

Usage:
    python main.py

Requirements:
    - Python 3.8+
    - Reddit API credentials in config.ini
    - Required packages (see requirements.txt)
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from gui.main_window import RedditRaffleTool
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all required packages are installed:")
    print("pip install praw pandas openpyxl")
    sys.exit(1)


def check_config():
    """Check if config.ini exists and provide setup instructions if not."""
    config_path = os.path.join(os.path.dirname(current_dir), "config.ini")
    if not os.path.exists(config_path):
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        
        message = """Reddit API Configuration Required

The config.ini file is missing. To use this application, you need to:

1. Go to https://www.reddit.com/prefs/apps
2. Create a new application (script type)
3. Copy config.ini.example to config.ini
4. Fill in your client_id and client_secret

The application will still work for the user database features,
but Reddit post parsing will not be available until configured.

Would you like to continue anyway?"""
        
        if not messagebox.askyesno("Configuration Missing", message):
            sys.exit(0)
        
        root.destroy()


def main():
    """Main application entry point."""
    print("Starting Reddit Raffle Tool...")
    print("Checking configuration...")
    
    check_config()
    
    try:
        # Create and run the application
        app = RedditRaffleTool()
        print("Application started successfully!")
        app.run()
        
    except Exception as e:
        print(f"Error starting application: {e}")
        
        # Show error dialog if possible
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Application Error", f"Failed to start application:\n{e}")
            root.destroy()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()