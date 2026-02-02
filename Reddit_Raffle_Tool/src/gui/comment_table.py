"""
Enhanced comment viewer with Excel-like table interface for displaying Reddit comments.
Supports inline editing of PayPal and Discord names that sync with the user database.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import sys
import os

# Try to import PIL for better image handling, fall back to tkinter if not available
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.manager import UserDatabase


class CommentTableViewer:
    def __init__(self, parent_frame, user_database: UserDatabase, refresh_callback=None, summary_widgets=None):
        """Initialize the comment table viewer."""
        self.parent_frame = parent_frame
        self.user_database = user_database
        self.comments_data = []
        self.filtered_bots = ['BotAndHisBoy', 'WatchURaffle', 'raffle_verification']
        self.all_comments_data = []  # Store all comments for searching
        self.search_var = None
        self.search_window = None
        self.refresh_callback = refresh_callback  # Callback to refresh main database tab
        self.post_price = 0.0  # Store price per item from post title
        self.total_spots = 0   # Store total spots from post title
        
        # Summary widgets from main window
        self.summary_widgets = summary_widgets or {}
        
        # Store additional column data for each comment
        self.comment_additional_data = {}  # item_id -> {tabbed: bool, user: str, spots: int, confirmed: bool}
        
        # Load checkmark image
        self.checkmark_image = None
        self.load_checkmark_image()
        
        # Initialize search navigation variables
        self.current_matches = []
        self.current_match_index = 0
        
        self.setup_table()
        self.setup_search_functionality()
        
    def load_checkmark_image(self):
        """Load the checkmark image for confirmed status."""
        try:
            # Get the path to the checkmark image
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            image_path = os.path.join(current_dir, "Images", "checkmark.png")
            
            if os.path.exists(image_path):
                if PIL_AVAILABLE:
                    try:
                        # Use PIL for better quality
                        pil_image = Image.open(image_path)
                        # Resize to fit in table cell (16x16 pixels)
                        pil_image = pil_image.resize((16, 16), Image.Resampling.LANCZOS)
                        self.checkmark_image = ImageTk.PhotoImage(pil_image)
                        print("✓ Loaded checkmark image using PIL")
                    except Exception as e:
                        print(f"PIL failed, using tkinter fallback: {e}")
                        # Fall back to tkinter's PhotoImage
                        self.checkmark_image = tk.PhotoImage(file=image_path)
                        # Subsample to make it smaller
                        self.checkmark_image = self.checkmark_image.subsample(2, 2)
                else:
                    # Use tkinter's PhotoImage
                    self.checkmark_image = tk.PhotoImage(file=image_path)
                    # Subsample to make it smaller
                    self.checkmark_image = self.checkmark_image.subsample(2, 2)
                    print("✓ Loaded checkmark image using tkinter")
            else:
                print(f"Checkmark image not found at: {image_path}")
                self.checkmark_image = None
        except Exception as e:
            print(f"Error loading checkmark image: {e}")
            self.checkmark_image = None
        
    def setup_table(self):
        """Set up the Excel-like table for displaying comments."""
        # Create search bar frame
        self.search_frame = ttk.Frame(self.parent_frame)
        self.search_frame.pack(fill="x", padx=10, pady=(5, 0))
        
        # Add search entry with placeholder-like styling
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(self.search_frame, textvariable=self.filter_var, width=30)
        self.filter_entry.pack(side="left", padx=(0, 10))
        self.filter_entry.bind("<KeyRelease>", self.on_filter_change)
        
        # Add placeholder text effect
        self.filter_entry.insert(0, "Search comments...")
        self.filter_entry.bind("<FocusIn>", self.on_filter_focus_in)
        self.filter_entry.bind("<FocusOut>", self.on_filter_focus_out)
        self.filter_placeholder_active = True
        
        # Add info label showing filter results
        self.filter_info_label = ttk.Label(self.search_frame, text="")
        self.filter_info_label.pack(side="right")
        
        # Create frame for the table
        self.table_frame = ttk.Frame(self.parent_frame)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=(5, 5))
        
        # Create Treeview widget (acts like Excel table) - no fixed height so it can expand
        self.tree = ttk.Treeview(self.table_frame, columns=("time", "reddit_user", "paypal", "comment"), show="headings")
        
        # Define column headings with visual indicators for editable columns
        self.tree.heading("time", text="Time (EST)")
        self.tree.heading("reddit_user", text="Reddit Username") 
        self.tree.heading("paypal", text="PayPal Name 📝")  # Visual indicator for editable
        self.tree.heading("comment", text="Comment")
        
        # Configure column widths and disable resizing/movement
        self.tree.column("time", width=120, minwidth=120, anchor="w", stretch=False)
        self.tree.column("reddit_user", width=150, minwidth=150, anchor="w", stretch=False)
        self.tree.column("paypal", width=150, minwidth=150, anchor="w", stretch=False)
        self.tree.column("comment", width=500, minwidth=500, anchor="w", stretch=False)
        
        # Apply dark theme styling to match the rest of the application
        self.apply_dark_theme_styling()
        
        # Create scrollbars that only appear when needed
        v_scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        
        # Configure tree to control scrollbars
        self.tree.configure(yscrollcommand=self.autohide_v_scrollbar, xscrollcommand=self.autohide_h_scrollbar)
        self.v_scrollbar = v_scrollbar
        self.h_scrollbar = h_scrollbar
        
        # Pack table first
        self.tree.pack(side="left", fill="both", expand=True)
        
        # Bind double-click event for editing
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # Also bind single click to show which cells are editable
        self.tree.bind("<Button-1>", self.on_single_click)
        
        # Bind click outside table to deselect
        self.parent_frame.bind("<Button-1>", self.on_click_outside)
    
    def autohide_v_scrollbar(self, first, last):
        """Auto-hide vertical scrollbar when not needed."""
        first, last = float(first), float(last)
        if first <= 0.0 and last >= 1.0:
            self.v_scrollbar.pack_forget()
        else:
            self.v_scrollbar.pack(side="right", fill="y")
        self.v_scrollbar.set(first, last)
    
    def autohide_h_scrollbar(self, first, last):
        """Auto-hide horizontal scrollbar when not needed."""
        first, last = float(first), float(last)
        if first <= 0.0 and last >= 1.0:
            self.h_scrollbar.pack_forget()
        else:
            self.h_scrollbar.pack(side="bottom", fill="x")
        self.h_scrollbar.set(first, last)
        
    def update_summary(self):
        """Update the financial summary panel with current totals."""
        if not self.summary_widgets or not hasattr(self, 'comments_data') or not self.comments_data:
            return
        
        # Use the total spots from the post title, not from individual entries
        total_spots = self.total_spots
        total_value = total_spots * self.post_price
        
        # Update main window summary widgets with basic info
        widgets = self.summary_widgets
        
        if 'post_info' in widgets and self.post_price > 0 and total_spots > 0:
            widgets['post_info'].config(text=f"{total_spots} Spots @ ${self.post_price:.2f}/ea")
        elif 'post_info' in widgets:
            widgets['post_info'].config(text="No pricing info available")
            
        if 'total' in widgets:
            widgets['total'].config(text=f"Total: ${total_value:.2f}")
            
        # Since we removed confirmation functionality, show simplified info
        if 'confirmed' in widgets:
            widgets['confirmed'].config(text=f"Comments loaded: {len(self.comments_data)}")
            
        if 'spots' in widgets:
            widgets['spots'].config(text=f"Official spots: {total_spots}")
            
        if 'remaining' in widgets:
            widgets['remaining'].config(text=f"Target value: ${total_value:.2f}")
            widgets['remaining'].config(foreground="white")  # Reset color
        
        # Simplified summary since we removed detailed tracking
        if 'progress_bar' in widgets:
            widgets['progress_bar']['value'] = 0  # Reset since no tracking
            
        if 'percentage' in widgets:
            widgets['percentage'].config(text="0.0%")  # Reset since no tracking
        
    def setup_search_functionality(self):
        """Set up Ctrl+F search functionality."""
        # Bind Ctrl+F to open search dialog
        self.parent_frame.bind_all("<Control-f>", self.open_search_dialog)
        # (Removed Ctrl+P bulk confirmation since we no longer have confirmation functionality)
        self.parent_frame.focus_set()  # Make sure the frame can receive key events
    
    def apply_dark_theme_styling(self):
        """Apply dark theme styling to match sv-ttk dark theme."""
        style = ttk.Style()
        
        # Configure Treeview to match dark theme with alternating colors
        style.configure("Treeview",
                       background="#2d2d30",
                       foreground="#ffffff",
                       fieldbackground="#2d2d30",
                       borderwidth=0,
                       relief="flat")
        
        # Configure alternating row colors
        self.tree.tag_configure("oddrow", background="#2d2d30")
        self.tree.tag_configure("evenrow", background="#3a4a3a")  # Light green-grey
        
        # Configure Treeview headings
        style.configure("Treeview.Heading",
                       background="#404040",
                       foreground="#ffffff",
                       relief="flat",
                       borderwidth=1)
        
        # Configure selection colors
        style.map("Treeview",
                 background=[('selected', '#0078d4')],
                 foreground=[('selected', '#ffffff')])
        
        style.map("Treeview.Heading",
                 background=[('active', '#505050')])
    
    def extract_price_from_title(self, title: str) -> float:
        """Extract price per item from post title (e.g., '$10/ea', '$5 ea', '@$15/each')."""
        import re
        
        # Common patterns for price per item - comprehensive list to handle variations
        patterns = [
            # Standard formats
            r'\$(\d+(?:\.\d{2})?)\s*per\s*spot',      # $5 per spot
            r'\$(\d+(?:\.\d{2})?)\s*/\s*spot',        # $5/spot, $5 / spot
            r'(\d+(?:\.\d{2})?)\s*dollars?\s*per\s*spot', # 5 dollars per spot
            r'(\d+(?:\.\d{2})?)\s*each\s*spot',       # 5 each spot
            
            # With "at" prefix
            r'at\s*\$(\d+(?:\.\d{2})?)\s*per\s*spot', # at $5 per spot
            r'at\s*\$(\d+(?:\.\d{2})?)\s*/\s*spot',   # at $5/spot
            r'at\s*\$(\d+(?:\.\d{2})?)\s*each',       # at $5 each
            r'at\s*\$(\d+(?:\.\d{2})?)',              # at $5
            
            # Standard ea/each formats
            r'\$(\d+(?:\.\d{2})?)/ea',                # $10/ea, $10.50/ea
            r'\$(\d+(?:\.\d{2})?)\s*ea',              # $10 ea, $10.50 ea
            r'\$(\d+(?:\.\d{2})?)/each',              # $10/each
            r'\$(\d+(?:\.\d{2})?)\s*each',            # $10 each
            
            # Special symbols and formats
            r'@\s*\$(\d+(?:\.\d{2})?)/each',          # @$15/each
            r'@\s*\$(\d+(?:\.\d{2})?)',               # @ $10
            r'(\d+(?:\.\d{2})?)\$/ea',                # 10$/ea
            
            # Alternative wordings
            r'(\d+(?:\.\d{2})?)\s*bucks?\s*per\s*spot', # 5 bucks per spot
            r'(\d+(?:\.\d{2})?)\s*per\s*entry',       # 5 per entry
            r'\$(\d+(?:\.\d{2})?)\s*per\s*entry',     # $5 per entry
            
            # Pipe separated formats (common in raffle titles)
            r'\|\s*(\d+)\s*spots?\s*at\s*\$(\d+(?:\.\d{2})?)', # | 76 spots at $5
            r'\|\s*\$(\d+(?:\.\d{2})?)\s*per',        # | $5 per
            r'\|\s*\$(\d+(?:\.\d{2})?)/spot',         # | $5/spot
            
            # Cost variations
            r'cost[s]?:\s*\$(\d+(?:\.\d{2})?)',      # cost: $5, costs: $5
            r'price[s]?:\s*\$(\d+(?:\.\d{2})?)',     # price: $5, prices: $5
            
            # Bracket formats
            r'\[\s*\$(\d+(?:\.\d{2})?)\s*\]',        # [$5]
            r'\(\s*\$(\d+(?:\.\d{2})?)\s*\)',        # ($5)
            
            # Multiple word variations
            r'(\d+(?:\.\d{2})?)\s*dollar[s]?\s*each', # 5 dollars each
            r'(\d+(?:\.\d{2})?)\s*buck[s]?\s*each',   # 5 bucks each
            
            # Slash variations
            r'(\d+(?:\.\d{2})?)\$/spot',              # 5$/spot
            r'(\d+(?:\.\d{2})?)\$\s*per\s*spot',     # 5$ per spot
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    # Handle special case where pattern captures both spots and price
                    if r'(\d+)\s*spots?\s*at\s*\$(\d+(?:\.\d{2})?)' in pattern:
                        # This pattern captures spots first, then price - we want the price (group 2)
                        return float(match.group(2))
                    else:
                        # Normal case - price is in group 1
                        return float(match.group(1))
                except ValueError:
                    continue
                except IndexError:
                    continue
        
        return 0.0
    
    def extract_spots_from_title(self, title: str) -> int:
        """Extract total number of spots from post title (e.g., '50 spots', '100 Spots')."""
        import re
        
        # Common patterns for spot count - comprehensive list
        patterns = [
            # Standard formats
            r'(\d+)\s+spots?',              # "50 spots" or "50 spot"
            r'(\d+)\s+Spots?',              # "50 Spots" or "50 Spot"  
            r'-\s*(\d+)\s+spots?',          # "- 50 spots"
            r'(\d+)spots?',                 # "50spots" (no space)
            
            # Pipe separated (common in raffle titles)
            r'\|\s*(\d+)\s+spots?',         # "| 76 spots"
            r'\|\s*(\d+)\s+Spots?',         # "| 76 Spots"
            
            # With prepositions
            r'with\s+(\d+)\s+spots?',       # "with 50 spots"
            r'has\s+(\d+)\s+spots?',        # "has 50 spots"
            r'of\s+(\d+)\s+spots?',         # "of 50 spots"
            
            # Alternative wordings
            r'(\d+)\s+entries?',            # "50 entries" or "50 entry"
            r'(\d+)\s+slots?',              # "50 slots" or "50 slot"
            r'(\d+)\s+positions?',          # "50 positions"
            
            # Bracket/parentheses formats
            r'\[\s*(\d+)\s+spots?\s*\]',    # "[50 spots]"
            r'\(\s*(\d+)\s+spots?\s*\)',    # "(50 spots)"
            
            # Number ranges (take the higher number)
            r'(\d+)-(\d+)\s+spots?',        # "45-50 spots" -> take 50
            r'up\s+to\s+(\d+)\s+spots?',    # "up to 50 spots"
            r'max\s+(\d+)\s+spots?',        # "max 50 spots"
            r'maximum\s+(\d+)\s+spots?',    # "maximum 50 spots"
            
            # Total variations
            r'total\s+(\d+)\s+spots?',      # "total 50 spots"
            r'(\d+)\s+total\s+spots?',      # "50 total spots"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    # Handle range patterns (take the higher number)
                    if r'(\d+)-(\d+)' in pattern and match.lastindex >= 2:
                        return max(int(match.group(1)), int(match.group(2)))
                    else:
                        # Normal case - spot count is in group 1
                        return int(match.group(1))
                except ValueError:
                    continue
                except IndexError:
                    continue
        
        return 0
    
    def calculate_total(self, spots: int) -> str:
        """Calculate total cost based on spots and price per item."""
        print(f"DEBUG calculate_total: spots={spots}, post_price={self.post_price}")
        if spots <= 0 or self.post_price <= 0:
            print(f"DEBUG: Returning empty string (spots={spots}, price={self.post_price})")
            return ""
        total = spots * self.post_price
        result = f"${total:.2f}" if total % 1 != 0 else f"${int(total)}"
        print(f"DEBUG: Calculated total: {result}")
        return result
    
    def save_current_state(self):
        """Save current user modifications (tabbed, confirmed, user assignments, spots) before refresh."""
        saved_state = {}
        
        # Iterate through all table items
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, "values")
            if len(values) >= 10:  # Ensure we have all columns
                reddit_user = values[1].split()[0]  # Remove validation indicator if present
                comment_text = values[4]  # Use comment text as additional identifier
                
                # Create a unique key combining username and comment text
                key = f"{reddit_user}||{comment_text}"
                
                # Get current values from additional data
                additional_data = self.comment_additional_data.get(item_id, {})
                
                saved_state[key] = {
                    "tabbed": values[5] != "",  # tabbed column
                    "user": values[6],  # user column 
                    "spots": values[7],  # spots column
                    "confirmed": values[9] != "",  # confirmed column
                    "additional_tabbed": additional_data.get("tabbed", False),
                    "additional_user": additional_data.get("user", ""),
                    "additional_spots": additional_data.get("spots", 0),
                    "additional_confirmed": additional_data.get("confirmed", False)
                }
        
        return saved_state
    
    def restore_saved_state(self, saved_state):
        """Restore user modifications after refresh."""
        if not saved_state:
            return
            
        # Iterate through current table items after refresh
        for item_id in self.tree.get_children():
            values = list(self.tree.item(item_id, "values"))
            if len(values) >= 10:
                reddit_user = values[1].split()[0]  # Remove validation indicator if present
                comment_text = values[4]
                
                # Create the same key used when saving
                key = f"{reddit_user}||{comment_text}"
                
                if key in saved_state:
                    state = saved_state[key]
                    
                    # Restore table values
                    values[5] = "✓" if state["tabbed"] else ""  # tabbed
                    values[6] = state["user"]  # user
                    values[7] = state["spots"]  # spots  
                    values[9] = "✓" if state["confirmed"] else ""  # confirmed
                    
                    # Update the table item
                    self.tree.item(item_id, values=values)
                    
                    # Restore additional data
                    if item_id in self.comment_additional_data:
                        self.comment_additional_data[item_id].update({
                            "tabbed": state["additional_tabbed"],
                            "user": state["additional_user"],
                            "spots": state["additional_spots"],
                            "confirmed": state["additional_confirmed"]
                        })
        
    def load_comments(self, post_data: Dict, preserve_state=False, saved_state=None):
        """Load comments from Reddit post data into the table with validation."""
        if "error" in post_data:
            self.show_error(post_data["error"])
            return
            
        # Extract price and spot count from post title
        post_title = post_data.get("title", "")
        self.post_price = self.extract_price_from_title(post_title)
        self.total_spots = self.extract_spots_from_title(post_title)
        
        print(f"DEBUG: Post title: '{post_title}'")
        print(f"DEBUG: Extracted price: ${self.post_price}")
        print(f"DEBUG: Extracted total spots: {self.total_spots}")
            
        # Clear existing data
        self.clear_table()
        self.comments_data = []
        self.all_comments_data = []  # Store all comments for filtering
        self.comment_additional_data = {}
        
        if "comments" not in post_data:
            self.show_message("No comments found in this post.")
            return
            
        # Check if we have validation data
        validation = post_data.get("validation")
        official_allocation = post_data.get("official_allocation", {})
        
        if validation:
            print(f"✓ Cross-validation enabled!")
            print(f"  Official spots: {validation['total_official_spots']}")
            print(f"  Parsed spots: {validation['total_parsed_spots']}")
            print(f"  Matches: {len(validation['matches'])}")
            print(f"  Mismatches: {len(validation['mismatches'])}")
            
            if validation['mismatches']:
                print("⚠ Mismatches found:")
                for mismatch in validation['mismatches']:
                    print(f"  - {mismatch['username']}: Official={mismatch['official_spots']}, Parsed={mismatch['parsed_spots']}")
        
        # Get post creation time for relative timing
        post_time = post_data.get("created_utc", 0)
        
        # Process and group comments by Reddit user
        comments_by_user = {}
        
        # First pass: organize comments by user
        for i, comment in enumerate(post_data["comments"]):
            # Skip bot comments
            if comment["author"] in self.filtered_bots:
                continue
                
            author = comment["author"]
            if author not in comments_by_user:
                comments_by_user[author] = []
            
            comments_by_user[author].append(comment)
        
        # Second pass: process each user's comments individually
        row_counter = 0
        user_color_index = 0  # Track color alternation by user, not by row
        user_colors = {}  # Map username to color
        
        for author, user_comments in comments_by_user.items():
            # Assign color to this user if not already assigned
            if author not in user_colors:
                user_colors[author] = "evenrow" if user_color_index % 2 == 0 else "oddrow"
                user_color_index += 1
            
            # Sort user's comments chronologically (earliest first)
            user_comments.sort(key=lambda c: c.get("created_utc", 0))
            
            for comment in user_comments:
                # Calculate EST time
                comment_time = comment.get("created_utc", 0)
                time_str = self.format_est_time(comment_time)
                
                # Get user data from database
                user_data = self.user_database.search_user(comment["author"])
                paypal_name = user_data["PayPal_Name"] if user_data else ""
                discord_name = user_data["Discord_Name"] if user_data else ""
                
                # Handle NaN values and display "-" for empty fields
                if paypal_name is None or str(paypal_name) == 'nan':
                    paypal_name = "-"
                else:
                    paypal_name = str(paypal_name) if paypal_name else "-"
                    
                if discord_name is None or str(discord_name) == 'nan':
                    discord_name = "-"
                else:
                    discord_name = str(discord_name) if discord_name else "-"
                
                # Clean and truncate comment text
                comment_text = self.clean_comment_text(comment.get("body", ""))
                
                # Use the exact spots detected for this specific comment
                auto_spots = comment.get("spots", 0)  # From parsed author replies for this specific comment
                
                # Store comment data for this individual comment
                comment_record = {
                    "time": time_str,
                    "reddit_user": comment["author"],
                    "paypal": paypal_name,
                    "discord": discord_name,
                    "comment": comment_text,
                    "created_utc": comment_time,
                    "score": comment.get("score", 0),
                    "auto_spots": auto_spots,  # Store spots for this specific comment
                    "official_spots": len(official_allocation.get(author, [])) if official_allocation else None,
                    "spot_numbers": official_allocation.get(author, []) if official_allocation else None
                }
                self.comments_data.append(comment_record)
                
                # Also store for filtering (with item_id reference for later)
                filter_record = comment_record.copy()
                self.all_comments_data.append(filter_record)
                
                # Insert individual comment into table
                tag = user_colors[author]  # Use the color assigned to this user
                
                # Add validation indicator if there was a mismatch for this user
                validation_indicator = ""
                if validation and official_allocation and author in official_allocation:
                    # Check if this user had any discrepancies (shown only once per user)
                    user_mismatches = [m for m in validation.get('mismatches', []) if m['username'] == author]
                    if user_mismatches:
                        validation_indicator = "✓"  # Indicates this user had corrections
                
                # Calculate total automatically if we have spots and price
                total_cost = self.calculate_total(auto_spots) if auto_spots > 0 else ""
                
                item_id = self.tree.insert("", "end", values=(
                    time_str,
                    comment["author"] + (" " + validation_indicator if validation_indicator else ""),
                    paypal_name,
                    comment_text
                ), tags=(tag,))
                
                # Initialize additional data for this specific comment
                self.comment_additional_data[item_id] = {
                    "tabbed": False,
                    "user": "",
                    "spots": auto_spots,  # Use spots for this specific comment
                    "confirmed": False,
                    "official_spots": len(official_allocation.get(author, [])) if official_allocation else None,
                    "spot_numbers": official_allocation.get(author, []) if official_allocation else None
                }
                
                row_counter += 1
            
        # Add missing users from official allocation (users who should have spots but weren't found in comments)
        if validation and validation['missing_users']:
            print(f"DEBUG: Adding {len(validation['missing_users'])} missing users from official allocation")
            
            for missing_user in validation['missing_users']:
                username = missing_user['username']
                official_spots = missing_user['official_spots']
                spot_numbers = missing_user['official_spot_numbers']
                
                # Get user data from database
                user_data = self.user_database.search_user(username)
                paypal_name = user_data["PayPal_Name"] if user_data else "-"
                discord_name = user_data["Discord_Name"] if user_data else "-"
                
                # Handle NaN values
                if paypal_name is None or str(paypal_name) == 'nan':
                    paypal_name = "-"
                else:
                    paypal_name = str(paypal_name) if paypal_name else "-"
                    
                if discord_name is None or str(discord_name) == 'nan':
                    discord_name = "-"
                else:
                    discord_name = str(discord_name) if discord_name else "-"
                
                # Create a record for this missing user
                comment_record = {
                    "time": "N/A",
                    "reddit_user": username,
                    "paypal": paypal_name,
                    "discord": discord_name,
                    "comment": f"[Missing from parsed comments] Official spots: {', '.join(map(str, spot_numbers))}",
                    "created_utc": 0,
                    "score": 0,
                    "auto_spots": official_spots,
                    "official_spots": official_spots,
                    "spot_numbers": spot_numbers
                }
                self.comments_data.append(comment_record)
                
                # Also store for filtering
                filter_record = comment_record.copy()
                self.all_comments_data.append(filter_record)
                
                # Insert into table
                # Assign color to missing user if not already assigned
                if username not in user_colors:
                    user_colors[username] = "evenrow" if user_color_index % 2 == 0 else "oddrow"
                    user_color_index += 1
                
                tag = user_colors[username]  # Use the color assigned to this user
                total_cost = self.calculate_total(official_spots) if official_spots > 0 else ""
                
                item_id = self.tree.insert("", "end", values=(
                    "N/A",
                    username + " ⚠",  # Warning indicator for missing user
                    paypal_name,
                    f"[Missing from comments] Spots: {', '.join(map(str, spot_numbers[:3]))}{'...' if len(spot_numbers) > 3 else ''}"
                ), tags=(tag,))
                
                # Initialize additional data
                self.comment_additional_data[item_id] = {
                    "tabbed": False,
                    "user": "",
                    "spots": official_spots,
                    "confirmed": False,
                    "official_spots": official_spots,
                    "spot_numbers": spot_numbers
                }
                
                row_counter += 1
            
        # Show summary with validation info
        total_comments = len(self.comments_data)
        validation_msg = ""
        if validation and validation.get('total_official_spots', 0) > 0:
            if validation['mismatches'] or validation['missing_users'] or validation['extra_users']:
                validation_msg = f" (✓ Cross-validated: {validation['total_official_spots']} official spots)"
            else:
                validation_msg = f" (✓ Validated: {validation['total_official_spots']} spots match)"
        elif official_allocation:
            validation_msg = f" (using official allocation: {sum(len(spots) for spots in official_allocation.values())} spots)"
        else:
            validation_msg = " (using parsed author replies only)"
        
        self.show_message(f"Loaded {total_comments} comments{validation_msg} (filtered out bot comments)")
        
        # Restore saved state if preserve_state is True
        if preserve_state and saved_state:
            self.restore_saved_state(saved_state)
            print("✓ Restored user modifications after refresh")
        
        # Update summary panel with pricing information
        self.update_summary()
        
    def format_est_time(self, utc_timestamp: float) -> str:
        """Format UTC timestamp as EST time (HH:MM:SS AM/PM)."""
        if utc_timestamp <= 0:
            return "00:00:00"
        
        # Convert UTC timestamp to datetime
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
        
        # Convert to EST (UTC-5) or EDT (UTC-4) depending on daylight saving time
        # For simplicity, we'll use a fixed UTC-5 offset (EST)
        est_offset = timedelta(hours=-5)
        est_dt = utc_dt + est_offset
        
        # Format as HH:MM:SS AM/PM
        return est_dt.strftime("%I:%M:%S %p")
        
    def clean_comment_text(self, text: str) -> str:
        """Clean and truncate comment text for display."""
        if not text:
            return ""
            
        # Remove excessive whitespace and newlines
        cleaned = " ".join(text.split())
        
        # Truncate if too long
        if len(cleaned) > 100:
            cleaned = cleaned[:97] + "..."
            
        return cleaned
        
    def on_single_click(self, event):
        """Handle single-click to show help text for editable columns."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        column = self.tree.identify_column(event.x)
        if column == "#3":
            self.show_message("💡 Double-click to edit PayPal name")
        elif column == "#4":
            self.show_message("💡 Double-click to edit Discord name")
        elif column == "#6":
            self.show_message("💡 Double-click to toggle Tabbed status (✓)")
        elif column == "#7":
            self.show_message("💡 Double-click to select User (autocomplete)")
        elif column == "#8":
            self.show_message("💡 Double-click to edit number of Spots")
        elif column == "#10":
            self.show_message("💡 Double-click to toggle Confirmed status (payment received)")
        
    def on_click_outside(self, event):
        """Handle clicking outside the table to deselect items."""
        # Check if the click was outside the treeview widget
        widget = event.widget
        if widget != self.tree:
            # Clear selection
            for item in self.tree.selection():
                self.tree.selection_remove(item)
        
    def on_double_click(self, event):
        """Handle double-click events for editing various columns."""
        # Get the item that was clicked
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        # Get the column that was clicked
        column = self.tree.identify_column(event.x)
        
        # Get more precise column information
        region = self.tree.identify_region(event.x, event.y)
        
        # Only proceed if we're clicking on a cell, not separator or heading
        if region != "cell":
            return
            
        print(f"Double-clicked item: {item}, column: {column}, region: {region}")  # Debug
        
        # Verify we have a valid column and item
        if not column or not item:
            return
            
        # Handle different columns with more precise targeting:
        # #3 = PayPal only (Discord removed)
        if column == "#3":  # PayPal column
            self.edit_column(item, column)
        else:
            print(f"Cannot edit column {column}")  # Debug
            return
    
    def edit_column(self, tree_item, column):
        """Create edit dialog or inline edit for different column types."""
        values = self.tree.item(tree_item, "values")
        if not values:
            return
            
        reddit_user = values[1]  # Reddit username column
        
        if column == "#3":  # PayPal Name
            self.edit_user_field(tree_item, column, reddit_user, values[2])
    
    def edit_user_field(self, tree_item, column, reddit_user: str, current_value: str):
        """Create edit dialog for PayPal name."""
        field_name = "PayPal Name"
        
        # Create popup dialog
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(f"Edit {field_name}")
        dialog.geometry("400x150")
        dialog.transient(self.parent_frame.winfo_toplevel())
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create form
        ttk.Label(dialog, text=f"Reddit User: {reddit_user}").pack(pady=5)
        ttk.Label(dialog, text=f"Edit {field_name}:").pack()
        
        entry = ttk.Entry(dialog, width=40)
        entry.pack(pady=5)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()
        
        # Button frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def save_changes():
            new_value = entry.get().strip()
            
            # Update database
            if column == "#3":  # PayPal
                success = self.user_database.update_user(reddit_user, paypal_name=new_value)
                if not success:
                    # User doesn't exist, add them
                    self.user_database.add_user(reddit_user, paypal_name=new_value)
            else:  # Discord
                success = self.user_database.update_user(reddit_user, discord_name=new_value)
                if not success:
                    # User doesn't exist, add them
                    self.user_database.add_user(reddit_user, discord_name=new_value)
            
            # Save database
            self.user_database.save_database()
            
            # Update ALL table rows for this user, not just the clicked one
            column_index = int(column[1:]) - 1  # Convert #3 to index 2, etc.
            updated_count = 0
            
            for item_id in self.tree.get_children():
                item_values = list(self.tree.item(item_id, "values"))
                # Check if this row belongs to the same Reddit user
                if len(item_values) > 1 and item_values[1].startswith(reddit_user):
                    # Remove any validation indicators (like "✓") from username for comparison
                    username = item_values[1].split()[0]  # Get just the username part
                    if username == reddit_user:
                        # Update this row
                        item_values[column_index] = new_value
                        current_tags = self.tree.item(item_id, "tags")
                        self.tree.item(item_id, values=item_values, tags=current_tags)
                        updated_count += 1
            
            # Also update the stored data for filtering
            if hasattr(self, 'all_comments_data'):
                for comment_data in self.all_comments_data:
                    if comment_data.get('reddit_user') == reddit_user:
                        if column == "#3":  # PayPal
                            comment_data['paypal'] = new_value
            
            # Also update comments_data
            if hasattr(self, 'comments_data'):
                for comment_data in self.comments_data:
                    if comment_data.get('reddit_user') == reddit_user:
                        if column == "#3":  # PayPal
                            comment_data['paypal'] = new_value
            
            # Trigger refresh of main database tab
            if self.refresh_callback:
                self.refresh_callback()
            
            dialog.destroy()
            self.show_message(f"Updated {field_name} for {reddit_user} ({updated_count} comments updated)")
            
        def cancel_changes():
            dialog.destroy()
            
        ttk.Button(btn_frame, text="Save", command=save_changes).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel_changes).pack(side="left", padx=5)
        
        # Bind Enter and Escape keys
        dialog.bind("<Return>", lambda e: save_changes())
        dialog.bind("<Escape>", lambda e: cancel_changes())
        
    def clear_table(self):
        """Clear all items from the table."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Reset filter to placeholder state
        if hasattr(self, 'filter_var'):
            self.filter_var.set("")
            if hasattr(self, 'filter_entry'):
                self.filter_entry.delete(0, tk.END)
                self.filter_entry.insert(0, "Search comments...")
                self.filter_placeholder_active = True
        if hasattr(self, 'filter_info_label'):
            self.filter_info_label.config(text="")
            
    def show_message(self, message: str):
        """Show a status message (now just prints to console since we removed status label)."""
        print(f"CommentTable: {message}")
        
    def open_search_dialog(self, event=None):
        """Open search dialog for finding users."""
        if self.search_window and self.search_window.winfo_exists():
            self.search_window.lift()
            self.search_window.focus()
            return
            
        self.search_window = tk.Toplevel(self.parent_frame)
        self.search_window.title("Search Users")
        self.search_window.geometry("350x80")
        self.search_window.resizable(False, False)
        self.search_window.transient(self.parent_frame.winfo_toplevel())
        
        # Center the dialog
        self.search_window.update_idletasks()
        x = (self.search_window.winfo_screenwidth() // 2) - (175)
        y = (self.search_window.winfo_screenheight() // 2) - (40)
        self.search_window.geometry(f"350x80+{x}+{y}")
        
        # Create search interface
        main_frame = ttk.Frame(self.search_window, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text="Search for user (Reddit, PayPal, or Discord name):").pack(pady=(0, 5))
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(main_frame, textvariable=self.search_var, width=35)
        search_entry.pack(pady=(0, 10))
        search_entry.bind("<KeyRelease>", self.perform_search)
        search_entry.bind("<Return>", self.perform_search_and_navigate)
        search_entry.focus()
        
        # Bind Escape and window close to close dialog
        self.search_window.bind("<Escape>", lambda e: self.close_search())
        self.search_window.protocol("WM_DELETE_WINDOW", self.close_search)
        
    def perform_search(self, event=None):
        """Perform search and highlight matching rows."""
        if not hasattr(self, 'search_var') or not self.search_var:
            return
            
        search_term = self.search_var.get().lower().strip()
        
        if not search_term:
            self.clear_search()
            return
            
        # Clear previous selection
        self.tree.selection_remove(self.tree.selection())
            
        # Find matching items
        matches = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if len(values) >= 4:
                reddit_user = values[1].lower()
                paypal_name = values[2].lower()
                discord_name = values[3].lower()
                
                if (search_term in reddit_user or 
                    search_term in paypal_name or 
                    search_term in discord_name):
                    matches.append(item)
                    
        # Store matches for navigation
        self.current_matches = matches
        self.current_match_index = 0
                    
        if matches:
            # Select all matches
            for match in matches:
                self.tree.selection_add(match)
            
            self.show_message(f"Found {len(matches)} match(es) for '{search_term}' - Press Enter to navigate")
        else:
            self.current_matches = []
            self.show_message(f"No matches found for '{search_term}'")
    
    def perform_search_and_navigate(self, event=None):
        """Perform search and navigate to the first/next result."""
        # First perform the search
        self.perform_search(event)
        
        # If we have matches, navigate to them
        if hasattr(self, 'current_matches') and self.current_matches:
            # Clear previous selection
            self.tree.selection_remove(self.tree.selection())
            
            # Select and focus on current match
            current_item = self.current_matches[self.current_match_index]
            self.tree.selection_set(current_item)
            self.tree.focus(current_item)
            self.tree.see(current_item)
            
            # Move to next match for subsequent presses
            self.current_match_index = (self.current_match_index + 1) % len(self.current_matches)
            
            match_num = (self.current_match_index if self.current_match_index > 0 
                        else len(self.current_matches))
            self.show_message(f"Match {match_num}/{len(self.current_matches)} - Press Enter for next")
            
            # Close search dialog after navigating
            self.close_search()
            
    def clear_search(self):
        """Clear search results and selection."""
        if hasattr(self, 'search_var') and self.search_var:
            self.search_var.set("")
        
        # Clear selection and match tracking
        self.tree.selection_remove(self.tree.selection())
        self.current_matches = []
        self.current_match_index = 0
        self.show_message("Search cleared")
        
    def close_search(self):
        """Close the search dialog."""
        if self.search_window and self.search_window.winfo_exists():
            self.search_window.destroy()
        self.search_window = None
        
    def show_error(self, error: str):
        """Show an error message."""
        print(f"CommentTable Error: {error}")


# Test function
    def refresh_user_autocomplete(self):
        """Refresh user autocomplete data from the database (simplified since we removed complex autocomplete)."""
        # This method is called by main_window but since we simplified the interface,
        # we just provide an empty implementation to avoid errors
        pass

    def on_filter_change(self, event=None):
        """Handle changes to the filter text."""
        # Don't filter if placeholder text is active
        if self.filter_placeholder_active:
            return
            
        filter_text = self.filter_var.get().lower().strip()
        self.apply_filter(filter_text)
    
    def on_filter_focus_in(self, event=None):
        """Handle focus in - remove placeholder text."""
        if self.filter_placeholder_active:
            self.filter_entry.delete(0, tk.END)
            self.filter_placeholder_active = False
    
    def on_filter_focus_out(self, event=None):
        """Handle focus out - restore placeholder if empty."""
        if not self.filter_var.get().strip():
            self.filter_entry.delete(0, tk.END)
            self.filter_entry.insert(0, "Search comments...")
            self.filter_placeholder_active = True
            # Clear any active filter when placeholder is restored
            self.apply_filter("")
    
    def apply_filter(self, filter_text):
        """Apply filter to the table based on search text."""
        if not hasattr(self, 'all_comments_data'):
            return
            
        # Clear current table
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not filter_text:
            # Show all comments if filter is empty
            self.load_filtered_comments(self.all_comments_data)
            self.filter_info_label.config(text="")
        else:
            # Filter comments based on search text
            filtered_data = []
            for comment_data in self.all_comments_data:
                # Search in multiple fields
                search_fields = [
                    str(comment_data.get('reddit_user', '')).lower(),
                    str(comment_data.get('paypal', '')).lower(),
                    str(comment_data.get('comment', '')).lower(),
                    str(comment_data.get('time', '')).lower()
                ]
                
                # Check if filter text appears in any field
                if any(filter_text in field for field in search_fields):
                    filtered_data.append(comment_data)
            
            # Load filtered results
            self.load_filtered_comments(filtered_data)
            
            # Update info label
            total_comments = len(self.all_comments_data)
            filtered_count = len(filtered_data)
            self.filter_info_label.config(text=f"Showing {filtered_count} of {total_comments} comments")
    
    def load_filtered_comments(self, comments_data):
        """Load comments into the table with proper user grouping colors."""
        if not comments_data:
            return
            
        # Group by user and assign colors
        users_seen = {}
        user_color_index = 0
        
        for comment_data in comments_data:
            username = comment_data.get('reddit_user', '')
            
            # Assign color to user if not seen before
            if username not in users_seen:
                users_seen[username] = "evenrow" if user_color_index % 2 == 0 else "oddrow"
                user_color_index += 1
            
            tag = users_seen[username]
            
            # Insert into table
            item_id = self.tree.insert("", "end", values=(
                comment_data.get('time', ''),
                comment_data.get('reddit_user', ''),
                comment_data.get('paypal', ''),
                comment_data.get('comment', '')
            ), tags=(tag,))
            
            # Restore additional data if it exists
            if hasattr(self, 'comment_additional_data') and comment_data.get('original_item_id'):
                original_id = comment_data['original_item_id']
                if original_id in self.comment_additional_data:
                    self.comment_additional_data[item_id] = self.comment_additional_data[original_id]

def test_comment_table():
    """Test the comment table viewer."""
    root = tk.Tk()
    root.title("Comment Table Test")
    root.geometry("800x600")
    
    # Create user database
    db = UserDatabase("test_database.xlsx")
    
    # Create comment table
    table = CommentTableViewer(root, db)
    
    # Sample test data
    test_data = {
        "title": "Test Post",
        "author": "test_author",
        "created_utc": 1695000000,
        "comments": [
            {
                "author": "took269",
                "body": "spot 3, 13",
                "created_utc": 1695000037,
                "score": 1
            },
            {
                "author": "makichan_",
                "body": "6,16,1,18",
                "created_utc": 1695000056,
                "score": 1
            },
            {
                "author": "BotAndHisBoy",  # This should be filtered out
                "body": "Winner is [5]",
                "created_utc": 1695000100,
                "score": 1
            }
        ]
    }
    
    table.load_comments(test_data)
    
    root.mainloop()


if __name__ == "__main__":
    test_comment_table()