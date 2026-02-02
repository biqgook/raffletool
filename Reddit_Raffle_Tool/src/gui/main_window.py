"""
Main window for the Reddit Raffle Tool with enhanced Excel-like comment display.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys
import sv_ttk
import platform

# Import pywinstyles for Windows title bar theming (Windows only)
if platform.system() == "Windows":
    try:
        import pywinstyles
    except ImportError:
        pywinstyles = None
else:
    pywinstyles = None

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from reddit.parser import RedditParser
from data.manager import UserDatabase
from gui.comment_table import CommentTableViewer


class RedditRaffleTool:
    def __init__(self):
        """Initialize the Reddit Raffle Tool main window."""
        self.root = tk.Tk()
        self.root.title("Reddit Raffle Tool - Enhanced")
        
        # Apply sv-ttk theme (dark mode by default)
        sv_ttk.set_theme("dark")
        
        # Apply dark title bar on Windows
        self.apply_theme_to_titlebar()
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Initialize components
        self.reddit_parser = RedditParser()
        self.user_database = UserDatabase()
        
        # Current post data
        self.current_post_data = None
        
        self.setup_ui()
        self.update_status()
        
    def setup_ui(self):
        """Set up the user interface."""
        # Create toolbar (just URL field)
        self.create_toolbar()
        
        # Create main content area with tabs
        self.create_notebook()
        
        # Create status bar
        self.create_status_bar()
        
        # Bind keyboard shortcuts
        self.root.bind("<Control-r>", lambda e: self.refresh_comments())
        self.root.bind("<Control-R>", lambda e: self.refresh_comments())
        self.root.bind("<Control-z>", lambda e: self.reset_application())
        self.root.bind("<Control-Z>", lambda e: self.reset_application())
        
    def create_menu(self):
        """Create the main menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Comments to Excel", command=self.export_comments)
        file_menu.add_command(label="Export Database to Excel", command=self.export_database)
        file_menu.add_separator()
        file_menu.add_command(label="Import Database from Excel", command=self.import_database)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Refresh Comments", command=self.refresh_comments, accelerator="Ctrl+R")
        edit_menu.add_separator()
        edit_menu.add_command(label="Reset Application", command=self.reset_application, accelerator="Ctrl+Z")
        edit_menu.add_separator()
        edit_menu.add_command(label="Validate with Official Allocation", command=self.validate_with_official_allocation)
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear Comments", command=self.clear_comments)
        edit_menu.add_command(label="Refresh Database", command=self.refresh_database)
        edit_menu.add_separator()
        
        # Theme submenu
        theme_menu = tk.Menu(edit_menu, tearoff=0)
        edit_menu.add_cascade(label="Theme", menu=theme_menu)
        theme_menu.add_command(label="Dark Theme", command=lambda: self.set_theme("dark"))
        theme_menu.add_command(label="Light Theme", command=lambda: self.set_theme("light"))
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
    def create_toolbar(self):
        """Create the simplified toolbar with just Reddit URL input."""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=10, pady=10)
        
        # URL input
        ttk.Label(toolbar, text="Reddit Post URL:", font=("Arial", 10)).pack(side="left", padx=(0, 10))
        
        self.url_entry = ttk.Entry(toolbar, width=80, font=("Arial", 10))
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self.parse_reddit_post())
        
        # Focus on the URL field when app starts
        self.url_entry.focus()
        
    def create_notebook(self):
        """Create the main notebook with tabs."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Comments tab with Excel-like table
        self.create_comments_tab()
        
        # User database tab
        self.create_database_tab()
        
    def create_comments_tab(self):
        """Create the comments tab with Excel-like table view."""
        comments_frame = ttk.Frame(self.notebook)
        self.notebook.add(comments_frame, text="📋 Comments Table")
        
        # Add header with post info (summary section removed)
        self.create_post_header(comments_frame)
        
        # Create comment table viewer without summary widgets
        self.comment_table = CommentTableViewer(comments_frame, self.user_database, 
                                               refresh_callback=self.refresh_database)
        
        self.comment_count_label = ttk.Label(comments_frame, text="No comments loaded")
        self.comment_count_label.pack(side="bottom", padx=10, pady=5)
        
    def create_post_header(self, parent):
        """Create header section with post information."""
        header_frame = ttk.LabelFrame(parent, text="Post Information", padding=10)
        header_frame.pack(fill="x", padx=10, pady=5)
        
        self.post_title_label = ttk.Label(header_frame, text="No post loaded", 
                                         font=("Arial", 11, "bold"))
        self.post_title_label.pack(anchor="w")
        
        self.post_info_label = ttk.Label(header_frame, text="", foreground="gray")
        self.post_info_label.pack(anchor="w")
        
        # Summary section removed for cleaner interface
        
    def create_database_tab(self):
        """Create the user database management tab."""
        db_frame = ttk.Frame(self.notebook)
        self.notebook.add(db_frame, text="👥 User Database")
        
        # Search frame
        search_frame = ttk.Frame(db_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 5))
        
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side="left", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", self.filter_database)
        
        ttk.Button(search_frame, text="Add User", command=self.add_user_dialog).pack(side="right")
        ttk.Button(search_frame, text="Delete Selected", command=self.delete_selected_user).pack(side="right", padx=(0, 5))
        
        # Database table
        self.create_database_table(db_frame)
        
        # Load database data
        self.refresh_database()
        
    def create_database_table(self, parent):
        """Create the user database table."""
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for database
        self.db_tree = ttk.Treeview(table_frame, columns=("paypal", "discord"), show="tree headings")
        
        self.db_tree.heading("#0", text="Reddit Username")
        self.db_tree.heading("paypal", text="PayPal Name")
        self.db_tree.heading("discord", text="Discord Name")
        
        self.db_tree.column("#0", width=200)
        self.db_tree.column("paypal", width=200)
        self.db_tree.column("discord", width=200)
        
        # Scrollbar for database table
        db_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.db_tree.yview)
        self.db_tree.configure(yscrollcommand=db_scrollbar.set)
        
        self.db_tree.pack(side="left", fill="both", expand=True)
        db_scrollbar.pack(side="right", fill="y")
        
        # Bind double-click for editing
        self.db_tree.bind("<Double-1>", self.edit_database_user)
        
    def create_status_bar(self):
        """Create the status bar."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill="x", side="bottom")
        
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side="left", padx=5)
        
        self.api_status_label = ttk.Label(self.status_frame, text="")
        self.api_status_label.pack(side="right", padx=5)
        
    def update_status(self):
        """Update the status bar with API status."""
        if self.reddit_parser.is_api_ready():
            self.api_status_label.config(text="Reddit API: ✓ Ready", foreground="green")
        else:
            self.api_status_label.config(text="Reddit API: ✗ Not configured", foreground="red")
            
    def parse_reddit_post(self, preserve_state=False, saved_state=None):
        """Parse a Reddit post and display comments in the table."""
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showwarning("Warning", "Please enter a Reddit post URL")
            return
            
        if not self.reddit_parser.is_api_ready():
            messagebox.showerror("Error", "Reddit API is not configured. Please check config.ini")
            return
            
        # Show parsing status
        self.status_label.config(text="Parsing Reddit post...")
        self.url_entry.config(state="disabled")  # Disable URL field during parsing
        self.root.update()
        
        # Parse in thread to avoid UI freezing
        def parse_thread():
            try:
                # Use validation-enabled parsing method
                post_data = self.reddit_parser.get_post_with_validation(url)
                
                # Update UI in main thread, passing along the state preservation parameters
                self.root.after(0, lambda: self.on_parse_complete(post_data, preserve_state, saved_state))
                
            except Exception as e:
                self.root.after(0, lambda: self.on_parse_error(str(e)))
                
        threading.Thread(target=parse_thread, daemon=True).start()
        
    def on_parse_complete(self, post_data, preserve_state=False, saved_state=None):
        """Handle completion of Reddit post parsing."""
        # Store the URL for refreshing
        post_data["url"] = self.url_entry.get().strip()
        self.current_post_data = post_data
        
        if "error" in post_data:
            messagebox.showerror("Error", f"Failed to parse post: {post_data['error']}")
            self.status_label.config(text="Ready")
        else:
            # Update post header
            self.post_title_label.config(text=post_data.get("title", "Unknown Title"))
            
            author = post_data.get("author", "Unknown")
            comment_count = len(post_data.get("comments", []))
            filtered_count = len([c for c in post_data.get("comments", []) 
                                if c["author"] not in ["BotAndHisBoy", "WatchURaffle", "raffle_verification"]])
            
            self.post_info_label.config(
                text=f"Author: {author} | Total Comments: {comment_count} | Displayed: {filtered_count}"
            )
            
            # Load comments into table
            if preserve_state and saved_state is not None:
                self.comment_table.load_comments(post_data, preserve_state, saved_state)
            else:
                self.comment_table.load_comments(post_data)
            
            # Update comment count
            self.comment_count_label.config(text=f"{filtered_count} comments loaded")
            
            self.status_label.config(text="Post parsed successfully")
            
        self.url_entry.config(state="normal")
        
    def on_parse_error(self, error_msg):
        """Handle Reddit post parsing errors."""
        messagebox.showerror("Error", f"Failed to parse post: {error_msg}")
        self.status_label.config(text="Ready")
        self.url_entry.config(state="normal")
        
    def clear_comments(self):
        """Clear the comments table."""
        self.comment_table.clear_table()
        self.current_post_data = None
        self.post_title_label.config(text="No post loaded")
        self.post_info_label.config(text="")
        self.comment_count_label.config(text="No comments loaded")
        self.status_label.config(text="Comments cleared")
        
    def reset_application(self):
        """Reset the application to initial state (Ctrl+Z shortcut)."""
        # Clear all current data
        self.clear_comments()
        
        # Clear the URL field
        self.url_entry.delete(0, tk.END)
        
        # Update status
        self.status_label.config(text="Application reset - ready to load new raffle")
        
        # Focus back to URL entry for convenience
        self.url_entry.focus_set()
        
    def refresh_comments(self):
        """Refresh comments from the current post while preserving user modifications."""
        if not self.current_post_data or "url" not in self.current_post_data:
            messagebox.showinfo("No Post", "No post loaded to refresh. Please parse a Reddit post first.")
            return
            
        # Save current user modifications before refreshing
        saved_state = self.comment_table.save_current_state()
        
        # Get the URL from current post data
        url = self.current_post_data["url"]
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, url)
        
        # Re-parse the post to get fresh comments
        self.status_label.config(text="Refreshing comments...")
        self.root.update_idletasks()
        
        try:
            # Parse the post fresh from Reddit
            self.parse_reddit_post(preserve_state=True, saved_state=saved_state)
            self.status_label.config(text="Comments refreshed successfully (user modifications preserved)")
        except Exception as e:
            self.status_label.config(text=f"Error refreshing comments: {e}")
            messagebox.showerror("Refresh Error", f"Failed to refresh comments: {e}")
        
    def refresh_database(self):
        """Refresh the database display sorted alphabetically by PayPal name."""
        # Clear existing items
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
            
        # Load all users and sort alphabetically by PayPal name
        users = self.user_database.get_all_users()
        
        # Sort users by PayPal name (empty names go to the end)
        def sort_key(user):
            paypal_name = user.get("PayPal_Name", "")
            # Handle NaN and non-string values
            if paypal_name is None or str(paypal_name) == 'nan':
                paypal_name = ""
            else:
                paypal_name = str(paypal_name).strip()
            # Put empty PayPal names at the end
            if not paypal_name:
                reddit_name = user.get("Reddit_Username", "")
                if reddit_name is None or str(reddit_name) == 'nan':
                    reddit_name = ""
                else:
                    reddit_name = str(reddit_name)
                return "zzz" + reddit_name.lower()
            return paypal_name.lower()
        
        sorted_users = sorted(users, key=sort_key)
        
        for user in sorted_users:
            # Handle NaN values for display
            reddit_username = user.get("Reddit_Username", "")
            if reddit_username is None or str(reddit_username) == 'nan':
                reddit_username = ""
            else:
                reddit_username = str(reddit_username)
                
            paypal_name = user.get("PayPal_Name", "")
            if paypal_name is None or str(paypal_name) == 'nan':
                paypal_name = "-"
            else:
                paypal_name = str(paypal_name)
                
            discord_name = user.get("Discord_Name", "")
            if discord_name is None or str(discord_name) == 'nan':
                discord_name = "-"
            else:
                discord_name = str(discord_name)
                
            self.db_tree.insert("", "end", 
                              text=reddit_username,
                              values=(paypal_name, discord_name))
        
        # Refresh autocomplete data in comment table if it exists
        if hasattr(self, 'comment_table') and self.comment_table:
            self.comment_table.refresh_user_autocomplete()
                              
    def filter_database(self, event=None):
        """Filter database based on search input, maintaining alphabetical order by PayPal name."""
        search_term = self.search_entry.get().lower()
        
        # Clear existing items
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
            
        # Load filtered users
        users = self.user_database.get_all_users()
        
        # Filter users based on search term
        filtered_users = []
        for user in users:
            # Handle NaN and non-string values safely
            reddit_user = user.get("Reddit_Username", "")
            if reddit_user is None or str(reddit_user) == 'nan':
                reddit_user = ""
            else:
                reddit_user = str(reddit_user).lower()
                
            paypal_name = user.get("PayPal_Name", "")
            if paypal_name is None or str(paypal_name) == 'nan':
                paypal_name = ""
            else:
                paypal_name = str(paypal_name).lower()
                
            discord_name = user.get("Discord_Name", "")
            if discord_name is None or str(discord_name) == 'nan':
                discord_name = ""
            else:
                discord_name = str(discord_name).lower()
            
            if (search_term in reddit_user or 
                search_term in paypal_name or 
                search_term in discord_name):
                filtered_users.append(user)
        
        # Sort filtered users alphabetically by PayPal name
        def sort_key(user):
            paypal_name = user.get("PayPal_Name", "")
            # Handle NaN and non-string values
            if paypal_name is None or str(paypal_name) == 'nan':
                paypal_name = ""
            else:
                paypal_name = str(paypal_name).strip()
            # Put empty PayPal names at the end
            if not paypal_name:
                reddit_name = user.get("Reddit_Username", "")
                if reddit_name is None or str(reddit_name) == 'nan':
                    reddit_name = ""
                else:
                    reddit_name = str(reddit_name)
                return "zzz" + reddit_name.lower()
            return paypal_name.lower()
        
        sorted_filtered_users = sorted(filtered_users, key=sort_key)
        
        # Display sorted filtered users
        for user in sorted_filtered_users:
            # Handle NaN values for display
            reddit_username = user.get("Reddit_Username", "")
            if reddit_username is None or str(reddit_username) == 'nan':
                reddit_username = ""
            else:
                reddit_username = str(reddit_username)
                
            paypal_name = user.get("PayPal_Name", "")
            if paypal_name is None or str(paypal_name) == 'nan':
                paypal_name = "-"
            else:
                paypal_name = str(paypal_name)
                
            discord_name = user.get("Discord_Name", "")
            if discord_name is None or str(discord_name) == 'nan':
                discord_name = "-"
            else:
                discord_name = str(discord_name)
                
            self.db_tree.insert("", "end",
                              text=reddit_username,
                              values=(paypal_name, discord_name))
                                  
    def add_user_dialog(self):
        """Show dialog to add a new user."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New User")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form fields
        ttk.Label(dialog, text="Reddit Username:").pack(pady=5)
        reddit_entry = ttk.Entry(dialog, width=40)
        reddit_entry.pack(pady=5)
        
        ttk.Label(dialog, text="PayPal Name:").pack(pady=5)
        paypal_entry = ttk.Entry(dialog, width=40)
        paypal_entry.pack(pady=5)
        
        ttk.Label(dialog, text="Discord Name:").pack(pady=5)
        discord_entry = ttk.Entry(dialog, width=40)
        discord_entry.pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def save_user():
            reddit_user = reddit_entry.get().strip()
            paypal_name = paypal_entry.get().strip()
            discord_name = discord_entry.get().strip()
            
            if not reddit_user:
                messagebox.showwarning("Warning", "Reddit username is required")
                return
                
            if self.user_database.add_user(reddit_user, paypal_name, discord_name):
                self.user_database.save_database()
                self.refresh_database()
                dialog.destroy()
                messagebox.showinfo("Success", f"Added user: {reddit_user}")
            else:
                messagebox.showerror("Error", f"User {reddit_user} already exists")
                
        ttk.Button(btn_frame, text="Save", command=save_user).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
        
        reddit_entry.focus()
        
    def edit_database_user(self, event):
        """Edit selected user in database."""
        selection = self.db_tree.selection()
        if not selection:
            return
            
        item = selection[0]
        reddit_user = self.db_tree.item(item, "text")
        values = self.db_tree.item(item, "values")
        
        # Similar dialog as add_user_dialog but for editing
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit User: {reddit_user}")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form fields with current values
        ttk.Label(dialog, text=f"Reddit Username: {reddit_user}").pack(pady=5)
        
        ttk.Label(dialog, text="PayPal Name:").pack(pady=5)
        paypal_entry = ttk.Entry(dialog, width=40)
        paypal_entry.pack(pady=5)
        paypal_entry.insert(0, values[0] if values else "")
        
        ttk.Label(dialog, text="Discord Name:").pack(pady=5)
        discord_entry = ttk.Entry(dialog, width=40)
        discord_entry.pack(pady=5)
        discord_entry.insert(0, values[1] if len(values) > 1 else "")
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def save_changes():
            paypal_name = paypal_entry.get().strip()
            discord_name = discord_entry.get().strip()
            
            self.user_database.update_user(reddit_user, paypal_name, discord_name)
            self.user_database.save_database()
            self.refresh_database()
            dialog.destroy()
            messagebox.showinfo("Success", f"Updated user: {reddit_user}")
            
        ttk.Button(btn_frame, text="Save", command=save_changes).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
        
        paypal_entry.focus()
        
    def delete_selected_user(self):
        """Delete selected user from database."""
        selection = self.db_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user to delete")
            return
            
        item = selection[0]
        reddit_user = self.db_tree.item(item, "text")
        
        if messagebox.askyesno("Confirm Delete", f"Delete user: {reddit_user}?"):
            if self.user_database.delete_user(reddit_user):
                self.user_database.save_database()
                self.refresh_database()
                messagebox.showinfo("Success", f"Deleted user: {reddit_user}")
                
    def show_about(self):
        """Show about dialog."""
        about_text = """Reddit Raffle Tool - Enhanced Version

Features:
• Excel-like comment display with inline editing
• Modern dark/light theme support
• Automatic bot comment filtering  
• User database management
• PayPal and Discord name linking
• Search functionality (Ctrl+F)
• Comment refresh (Ctrl+R)
• Export/import functionality

Controls:
• Double-click PayPal or Discord columns to edit
• Ctrl+F to search comments
• Ctrl+R to refresh comments
• Edit → Theme to switch themes

Changes are automatically saved to the database.

Version: 2.1 with sv-ttk themes
"""
        messagebox.showinfo("About Reddit Raffle Tool", about_text)
        
    def set_theme(self, theme_name):
        """Set the application theme."""
        try:
            sv_ttk.set_theme(theme_name)
            self.apply_theme_to_titlebar()  # Update title bar when theme changes
            self.status_label.config(text=f"Theme changed to {theme_name} mode")
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to set theme: {e}")
    
    def apply_theme_to_titlebar(self):
        """Apply theme to Windows title bar for better appearance."""
        if platform.system() != "Windows" or pywinstyles is None:
            return
            
        try:
            # Get current theme
            current_theme = sv_ttk.get_theme()
            
            # Check Windows version for compatibility
            import sys
            version = sys.getwindowsversion()
            
            if version.major == 10 and version.build >= 22000:
                # Windows 11 - full color support
                if current_theme == "dark":
                    pywinstyles.change_header_color(self.root, "#1c1c1c")
                else:
                    pywinstyles.change_header_color(self.root, "#fafafa")
            elif version.major == 10:
                # Windows 10 - limited to dark/light
                if current_theme == "dark":
                    pywinstyles.apply_style(self.root, "dark")
                else:
                    pywinstyles.apply_style(self.root, "normal")
            
            # Small delay to ensure the window is fully rendered
            self.root.after(100, lambda: self.root.wm_attributes("-alpha", 0.99))
            self.root.after(200, lambda: self.root.wm_attributes("-alpha", 1.0))
            
        except Exception as e:
            # Silently handle any errors with title bar theming
            print(f"Note: Could not apply title bar theme: {e}")

    def validate_with_official_allocation(self):
        """Show dialog to input official allocation data and validate against current comments."""
        if not self.current_post_data:
            messagebox.showwarning("Warning", "Please load Reddit comments first before validating.")
            return
        
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Official Spot Allocation Validation")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme
        if hasattr(self, 'current_theme'):
            sv_ttk.set_theme(self.current_theme)
        
        # Main frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Instructions
        instructions = ttk.Label(main_frame, 
            text="Paste the official spot allocation data below (format: '1 u/username PAID'):",
            font=("Segoe UI", 10))
        instructions.pack(anchor="w", pady=(0, 10))
        
        # Text area for input
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        text_widget = tk.Text(text_frame, wrap="word", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Pre-populate with example
        example_text = """1 u/False_Archer4193 PAID
2 u/SWBlegalpackage PAID
3 u/SWBGlove PAID
4 u/the_westgate PAID
5 u/Jealous_Ad9824 PAID
... (paste your official allocation here)"""
        text_widget.insert("1.0", example_text)
        text_widget.select_range("1.0", "end")
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        def validate_allocation():
            """Validate the input allocation against current comments."""
            allocation_text = text_widget.get("1.0", "end-1c").strip()
            if not allocation_text:
                messagebox.showwarning("Warning", "Please enter the official allocation data.")
                return
            
            try:
                # Parse the official allocation
                official_allocation = self.reddit_parser.parse_official_spot_allocation(allocation_text)
                
                if not official_allocation:
                    messagebox.showerror("Error", "No valid allocation data found. Please check the format.")
                    return
                
                # Create validation data similar to what get_post_with_validation does
                parsed_comments = []
                for comment_data in self.current_post_data.get("comments", []):
                    class CommentObj:
                        def __init__(self, username, spots):
                            self.reddit_username = username
                            self.auto_spots = spots
                    parsed_comments.append(CommentObj(comment_data["author"], comment_data.get("spots", 0)))
                
                # Validate
                validation = self.reddit_parser.validate_spot_assignments(parsed_comments, official_allocation)
                
                # Add validation data to current post data
                self.current_post_data["validation"] = validation
                self.current_post_data["official_allocation"] = official_allocation
                
                # Close dialog
                dialog.destroy()
                
                # Reload the comments table with validation data
                self.comment_table.load_comments(self.current_post_data)
                
                # Show validation results
                total_official = validation["total_official_spots"]
                total_parsed = validation["total_parsed_spots"]
                matches = len(validation["matches"])
                mismatches = len(validation["mismatches"])
                missing = len(validation["missing_users"])
                extra = len(validation["extra_users"])
                
                result_msg = f"Validation Complete!\n\n"
                result_msg += f"Official spots: {total_official}\n"
                result_msg += f"Parsed spots: {total_parsed}\n"
                result_msg += f"Matches: {matches}\n"
                result_msg += f"Mismatches: {mismatches}\n"
                result_msg += f"Missing users: {missing}\n"
                result_msg += f"Extra users: {extra}\n"
                
                if mismatches > 0:
                    result_msg += f"\nMismatches corrected automatically!"
                
                if missing > 0:
                    result_msg += f"\nMissing users added to table!"
                
                messagebox.showinfo("Validation Results", result_msg)
                
            except Exception as e:
                messagebox.showerror("Error", f"Error validating allocation: {str(e)}")
        
        ttk.Button(button_frame, text="Validate", command=validate_allocation).pack(side="right", padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="right")
        
        # Focus on text widget
        text_widget.focus_set()
        
    def run(self):
        """Start the application."""
        self.root.mainloop()


# Entry point
if __name__ == "__main__":
    app = RedditRaffleTool()
    app.run()