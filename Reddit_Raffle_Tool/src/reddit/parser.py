"""
Reddit API parser module for extracting post comments.
"""

import praw
import configparser
import os
from datetime import datetime
from typing import List, Dict, Optional


class RedditParser:
    def __init__(self, config_file: str = "config.ini"):
        """Initialize Reddit API connection."""
        self.reddit = None
        self.config_file = config_file
        self._initialize_reddit_api()

    def _initialize_reddit_api(self):
        """Initialize Reddit API with credentials from config file."""
        if not os.path.exists(self.config_file):
            print(f"Config file {self.config_file} not found. Please create it with Reddit API credentials.")
            return
        
        config = configparser.ConfigParser()
        config.read(self.config_file)
        
        try:
            self.reddit = praw.Reddit(
                client_id=config['reddit']['client_id'],
                client_secret=config['reddit']['client_secret'],
                user_agent=config['reddit']['user_agent']
            )
            print("Reddit API initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Reddit API: {e}")

    def extract_post_id_from_url(self, url: str) -> Optional[str]:
        """Extract Reddit post ID from URL."""
        # Handle various Reddit URL formats
        if '/comments/' in url:
            parts = url.split('/comments/')
            if len(parts) > 1:
                post_id = parts[1].split('/')[0]
                return post_id
        return None

    def get_post_comments(self, post_url: str) -> Dict:
        """
        Get comments from a Reddit post.
        Returns dictionary with post info and comments.
        """
        import re  # Import at the top of the method
        
        if not self.reddit:
            return {"error": "Reddit API not initialized"}

        post_id = self.extract_post_id_from_url(post_url)
        if not post_id:
            return {"error": "Invalid Reddit URL"}

        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=None)  # Load all comments
            
            post_info = {
                "title": submission.title,
                "author": submission.author.name if submission.author else "[deleted]",
                "created_utc": submission.created_utc,
                "url": post_url,
                "comments": []
            }
            
            # Extract all comments (including post author's replies for spot detection)
            author_spot_assignments = {}  # Map comment IDs to spot assignments
            removed_users = set()  # Track users who were removed for non-payment
            
            # First pass: Find all author replies, spot assignments, and removed users
            removal_context_active = False  # Track if we're in a removal context
            
            for comment in submission.comments.list():
                if comment.author and comment.author.name == post_info["author"]:
                    comment_body = comment.body.lower().strip()
                    print(f"DEBUG: Checking author comment: '{comment.body[:100]}...'")
                    
                    # Check for user removal patterns
                    if any(pattern in comment_body for pattern in [
                        "unpaid participants: your unpaid slots have been removed",
                        "removed due to lack of payment",
                        "slots have been removed",
                        "attention unpaid participants"
                    ]):
                        print(f"DEBUG: Found removal pattern in comment: '{comment.body}'")
                        removal_context_active = True
                        # Look for username mentions in this removal comment
                        mentioned_users = re.findall(r'u/(\w+)', comment.body)
                        print(f"DEBUG: Found mentioned users in removal comment: {mentioned_users}")
                        removed_users.update(mentioned_users)
                    
                    # Check if this is just a username mention (likely indicating removal)
                    # This is more likely to be a removal if we recently saw a removal announcement
                    username_only_pattern = r'^/?u/(\w+)$'
                    username_match = re.match(username_only_pattern, comment.body.strip())
                    if username_match:
                        username = username_match.group(1)
                        print(f"DEBUG: Found standalone username mention: {username}")
                        # Always treat standalone username mentions as removals (common pattern)
                        print(f"DEBUG: Adding {username} to removed users")
                        removed_users.add(username)
                    
                    # Check for spot assignments
                    spots = self.extract_spots_from_author_reply(comment.body)
                    if spots > 0:
                        # Find the parent comment to assign spots to
                        try:
                            parent_comment = comment.parent()
                            if hasattr(parent_comment, 'author') and parent_comment.author and hasattr(parent_comment, 'id'):
                                parent_comment_id = parent_comment.id
                                # Only assign spots if the user wasn't removed
                                if parent_comment.author.name not in removed_users:
                                    author_spot_assignments[parent_comment_id] = spots
                        except:
                            pass  # Skip if we can't get parent
            
            # Second pass: Extract user comments and apply spot assignments
            print(f"DEBUG: Removed users detected: {removed_users}")
            
            for comment in submission.comments.list():
                if comment.author and comment.author.name != post_info["author"]:
                    # Skip removed users
                    if comment.author.name in removed_users:
                        print(f"DEBUG: Skipping removed user: {comment.author.name}")
                        continue
                    
                    # Regular user comment
                    spots_assigned = author_spot_assignments.get(comment.id, 0)
                    comment_data = {
                        "author": comment.author.name,
                        "body": comment.body,
                        "created_utc": comment.created_utc,
                        "score": comment.score,
                        "id": comment.id,
                        "spots": spots_assigned  # Add spots from author reply
                    }
                    post_info["comments"].append(comment_data)
            
            # Sort comments by creation time (chronological order)
            post_info["comments"].sort(key=lambda x: x["created_utc"])
            
            return post_info
            
        except Exception as e:
            return {"error": f"Failed to fetch post: {e}"}

    def extract_spots_from_author_reply(self, reply_text: str) -> int:
        """
        Extract number of spots from author's reply.
        Examples:
        - "You got 88" -> 1 spot
        - "You got 46, 78, 84, 44, 60, 85, 63, 81, 65, 69" -> 10 spots
        - "You got 2 spots" -> 2 spots
        """
        import re
        
        # Clean the text and convert to lowercase
        text = reply_text.lower().strip()
        
        # DEBUG: Print what we're analyzing
        print(f"DEBUG: Analyzing reply text: '{reply_text}'")
        print(f"DEBUG: Cleaned text: '{text}'")
        
        # Check for explicit "X spots" pattern first (higher priority)
        spots_pattern = r'you got (\d+) spots?'
        spots_match = re.search(spots_pattern, text)
        if spots_match:
            result = int(spots_match.group(1))
            print(f"DEBUG: Found explicit spots pattern: {result}")
            return result
        
        # Pattern to match "you got" followed by numbers - BUT ONLY ON THE FIRST LINE
        if "you got" in text:
            # Split by newlines and only process the first line with "you got"
            lines = text.split('\n')
            you_got_line = None
            for line in lines:
                if "you got" in line:
                    you_got_line = line.strip()
                    break
            
            if you_got_line:
                # Extract everything after "you got" in that line only
                after_you_got = you_got_line.split("you got", 1)[1]
                
                # Stop at any common instruction markers
                stop_markers = ["please follow", "send payment", "after payment", "if you", "\n"]
                for marker in stop_markers:
                    if marker in after_you_got:
                        after_you_got = after_you_got.split(marker)[0]
                        break
                
                # Find all numbers in this limited text
                numbers = re.findall(r'\b\d+\b', after_you_got)
                
                print(f"DEBUG: You got line: '{you_got_line}'")
                print(f"DEBUG: After 'you got' (limited): '{after_you_got}'")
                print(f"DEBUG: Numbers found: {numbers}")
                
                if numbers:
                    # Count how many spot numbers were assigned
                    result = len(numbers)
                    print(f"DEBUG: Counting spot numbers: {result}")
                    return result
        
        # NEW: Check for casual spot assignment formats (no "you got" required)
        # Look for patterns like "16, 3" or "1, 2, 8, 9, 24, 11, 7, 25, 13, 14" on first line
        lines = text.split('\n')
        first_line = lines[0].strip() if lines else ""
        
        # Look for numbers in the first line - be more permissive
        if first_line:
            # First, try to find comma-separated numbers or standalone numbers
            number_patterns = [
                r'(\d+(?:\s*,\s*\d+)+)',      # Multiple comma-separated numbers: "16, 3" or "1, 2, 8, 9"
                r'\b(\d{1,2})\s*$',           # Single number at end of line: "17" or "STARTER 17"  
                r'\b(\d{1,2}(?:\s*,\s*\d{1,2})+)', # Numbers with potential spaces: "20, 21"
            ]
            
            for pattern in number_patterns:
                match = re.search(pattern, first_line)
                if match:
                    number_str = match.group(1)
                    # Extract individual numbers
                    individual_numbers = re.findall(r'\d+', number_str)
                    
                    # Filter out clearly non-spot numbers (like year 2024, large IDs, etc.)
                    valid_numbers = []
                    for num_str in individual_numbers:
                        num = int(num_str)
                        # Only consider reasonable spot numbers (1-100, since most raffles are smaller)
                        if 1 <= num <= 100:
                            valid_numbers.append(num_str)
                    
                    if valid_numbers and len(valid_numbers) > 0:
                        result = len(valid_numbers)
                        print(f"DEBUG: Found casual spot assignment on first line: '{first_line}'")
                        print(f"DEBUG: Extracted numbers: {valid_numbers}")
                        print(f"DEBUG: Counting {result} spots")
                        return result
            
            # Also check second line in case numbers are there
            if len(lines) > 1:
                second_line = lines[1].strip()
                for pattern in number_patterns:
                    match = re.search(pattern, second_line)
                    if match:
                        number_str = match.group(1)
                        individual_numbers = re.findall(r'\d+', number_str)
                        
                        # Filter out clearly non-spot numbers
                        valid_numbers = []
                        for num_str in individual_numbers:
                            num = int(num_str)
                            if 1 <= num <= 100:
                                valid_numbers.append(num_str)
                        
                        if valid_numbers and len(valid_numbers) > 0:
                            result = len(valid_numbers)
                            print(f"DEBUG: Found casual spot assignment on second line: '{second_line}'")
                            print(f"DEBUG: Extracted numbers: {valid_numbers}")
                            print(f"DEBUG: Counting {result} spots")
                            return result
        
        # Alternative patterns
        patterns = [
            r'assigned.*?(\d+)\s+spots?',  # "assigned 5 spots"
            r'(\d+)\s+spots?\s+assigned',  # "5 spots assigned"
            r'got\s+(\d+)\s+spots?',       # "got 3 spots"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                result = int(match.group(1))
                print(f"DEBUG: Found alternative pattern '{pattern}': {result}")
                return result
        
        print(f"DEBUG: No spots detected, returning 0")
        return 0  # No spots detected

    def parse_official_spot_allocation(self, post_body: str) -> Dict[str, List[int]]:
        """
        Parse the official spot allocation from the host's post body.
        Returns a dictionary mapping usernames to their allocated spot numbers.
        """
        import re
        
        allocation = {}
        
        # Multiple patterns for different allocation formats (try in order of specificity)
        patterns = [
            # Most specific first: "1 u/username PAID" - updated to handle hyphens and numbers in usernames
            r'(\d+)\s+u/([\w\-]+)\s+PAID',
            # Standard formats: "1 u/username" - updated to handle hyphens and numbers in usernames
            r'(\d+)\s+u/([\w\-]+)',
            # Pipe separated: "1 | u/username | PAID"
            r'(\d+)\s*\|\s*u/([\w\-]+)',
            # Table format: "1    u/username    PAID"
            r'^(\d+)\s+u/([\w\-]+)',
            # Numbered list: "1. u/username"
            r'(\d+)\.\s+u/([\w\-]+)',
            # Spot range: "1-3 u/username" (need to expand ranges)
            r'(\d+)-(\d+)\s+u/([\w\-]+)',
            # Multiple spots: "1, 5, 10 u/username"
            r'([\d,\s]+)\s+u/([\w\-]+)',
        ]
        
        # Try patterns in order until we find matches
        for pattern in patterns:
            matches = re.findall(pattern, post_body, re.MULTILINE)
            print(f"DEBUG: Pattern '{pattern}' found {len(matches)} matches")
            
            if matches:  # If we found matches with this pattern, use it and stop
                for match in matches:
                    if len(match) == 2:  # Single spot
                        try:
                            spot_num, username = match
                            spot_num = int(spot_num)
                            if username not in allocation:
                                allocation[username] = []
                            allocation[username].append(spot_num)
                            print(f"DEBUG: Added spot {spot_num} for user {username}")
                        except ValueError:
                            continue
                            
                    elif len(match) == 3 and pattern.endswith(r'(\w+)'):  # Range format
                        try:
                            start, end, username = match
                            start, end = int(start), int(end)
                            if username not in allocation:
                                allocation[username] = []
                            for spot in range(start, end + 1):
                                allocation[username].append(spot)
                            print(f"DEBUG: Added spots {start}-{end} for user {username}")
                        except ValueError:
                            continue
                
                # If we found matches, don't try other patterns
                if allocation:
                    break
        
        # Handle comma-separated spots
        for username in list(allocation.keys()):
            spots = allocation[username]
            expanded_spots = []
            for spot_entry in spots:
                if isinstance(spot_entry, str) and ',' in str(spot_entry):
                    # Parse comma-separated numbers
                    try:
                        numbers = [int(x.strip()) for x in str(spot_entry).split(',') if x.strip().isdigit()]
                        expanded_spots.extend(numbers)
                    except:
                        expanded_spots.append(spot_entry)
                else:
                    expanded_spots.append(spot_entry)
            allocation[username] = expanded_spots
        
        print(f"DEBUG: Final allocation parsed: {len(allocation)} users, {sum(len(spots) for spots in allocation.values())} total spots")
        return allocation

    def validate_spot_assignments(self, parsed_comments: List, official_allocation: Dict[str, List[int]]) -> Dict:
        """
        Validate parsed spot assignments against official allocation.
        Returns validation results and corrections.
        """
        validation_results = {
            "matches": [],
            "mismatches": [],
            "missing_users": [],
            "extra_users": [],
            "total_official_spots": 0,
            "total_parsed_spots": 0
        }
        
        # Calculate totals
        for username, spots in official_allocation.items():
            validation_results["total_official_spots"] += len(spots)
        
        # Create a map of parsed data
        parsed_allocation = {}
        for comment in parsed_comments:
            if hasattr(comment, 'auto_spots') and comment.auto_spots > 0:
                username = comment.reddit_username
                if username not in parsed_allocation:
                    parsed_allocation[username] = 0
                parsed_allocation[username] += comment.auto_spots
                validation_results["total_parsed_spots"] += comment.auto_spots
        
        # Compare allocations
        all_usernames = set(official_allocation.keys()) | set(parsed_allocation.keys())
        
        for username in all_usernames:
            official_count = len(official_allocation.get(username, []))
            parsed_count = parsed_allocation.get(username, 0)
            
            if username in official_allocation and username in parsed_allocation:
                if official_count == parsed_count:
                    validation_results["matches"].append({
                        "username": username,
                        "spots": official_count
                    })
                else:
                    validation_results["mismatches"].append({
                        "username": username,
                        "official_spots": official_count,
                        "parsed_spots": parsed_count,
                        "official_spot_numbers": official_allocation[username]
                    })
            elif username in official_allocation:
                validation_results["missing_users"].append({
                    "username": username,
                    "official_spots": official_count,
                    "official_spot_numbers": official_allocation[username]
                })
            else:
                validation_results["extra_users"].append({
                    "username": username,
                    "parsed_spots": parsed_count
                })
        
        return validation_results

    def get_post_with_validation(self, post_url: str) -> Dict:
        """
        Get post comments with cross-validation against official spot allocation.
        Automatically searches for official allocation in post body and author comments.
        """
        import re  # Import regex for pattern matching
        
        if not self.reddit:
            return {"error": "Reddit API not initialized"}

        post_id = self.extract_post_id_from_url(post_url)
        if not post_id:
            return {"error": "Invalid Reddit URL"}

        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=None)

            # Get the basic post data first
            basic_post_data = self.get_post_comments(post_url)
            if "error" in basic_post_data:
                return basic_post_data

            # Parse official allocation from multiple sources
            print("DEBUG: Searching for official spot allocation...")
            official_allocation = {}
            
            # 1. Check post body first
            if submission.selftext:
                official_allocation = self.parse_official_spot_allocation(submission.selftext)
                if official_allocation:
                    print(f"DEBUG: Found official allocation in post body with {len(official_allocation)} users")
            
            # 2. If not found in post body, search through ALL author's comments
            if not official_allocation:
                author_name = basic_post_data.get("author", "")
                print(f"DEBUG: Searching author ({author_name}) comments for official allocation...")
                
                # Look for patterns that indicate official allocation
                allocation_patterns = [
                    r'\d+\s+u/[\w\-]+\s+(?:PAID|paid)',  # "1 u/username PAID" - updated for hyphens
                    r'\d+\s+u/[\w\-]+\s*$',             # "1 u/username" - updated for hyphens
                    r'\d+\.\s+u/[\w\-]+',               # "1. u/username" - updated for hyphens
                    r'\|\s*\d+\s*\|\s*u/[\w\-]+',       # "| 1 | u/username |" - updated for hyphens
                    r'\d+\s*\|\s*u/[\w\-]+',            # "1 | u/username" - updated for hyphens
                ]
                
                # Also look for high-concentration comments (comments with many usernames)
                best_allocation = {}
                max_spots_found = 0
                
                for comment in submission.comments.list():
                    if comment.author and comment.author.name == author_name:
                        # Check if this comment contains allocation data
                        comment_body = comment.body
                        print(f"DEBUG: Checking author comment: '{comment_body[:100]}...'")
                        
                        # Count potential allocation lines in this comment
                        total_matches = 0
                        username_count = len(re.findall(r'u/[\w\-]+', comment_body))  # Updated for hyphens
                        
                        for pattern in allocation_patterns:
                            matches = re.findall(pattern, comment_body, re.MULTILINE | re.IGNORECASE)
                            total_matches += len(matches)
                        
                        print(f"DEBUG: Found {total_matches} allocation patterns, {username_count} usernames in this comment")
                        
                        # If we find multiple allocation-like lines OR many usernames
                        if total_matches > 3 or username_count > 10:  
                            print(f"DEBUG: Processing potential allocation comment with {total_matches} patterns, {username_count} usernames")
                            temp_allocation = self.parse_official_spot_allocation(comment_body)
                            total_spots = sum(len(spots) for spots in temp_allocation.values())
                            
                            if total_spots > max_spots_found:
                                best_allocation = temp_allocation
                                max_spots_found = total_spots
                                print(f"DEBUG: New best allocation found with {total_spots} total spots")
                
                official_allocation = best_allocation
                if official_allocation:
                    print(f"DEBUG: Final selection: {len(official_allocation)} users, {max_spots_found} total spots")
            # 3. If still not found, allow manual input for testing
            if not official_allocation:
                print("DEBUG: No automatic allocation found. Checking for manual test data...")
                # This is where we can inject the manual allocation for testing
                manual_allocation_text = """
1 u/shawnfinch2 PAID
2 u/allidoiswoof PAID
3 u/allidoiswoof PAID
4 u/allidoiswoof PAID
5 u/allidoiswoof PAID
6 u/allidoiswoof PAID
7 u/Jsh0 PAID
8 u/allidoiswoof PAID
9 u/krysterix PAID
10 u/SWBGlove PAID
11 u/Jsh0 PAID
12 u/allidoiswoof PAID
13 u/imjakemon PAID
14 u/allidoiswoof PAID
15 u/makichan_ PAID
16 u/imjakemon PAID
17 u/Jsh0 PAID
18 u/BigPersimmon1003 PAID
19 u/shawnfinch2 PAID
20 u/imjakemon PAID
21 u/imjakemon PAID
22 u/doublechen-94 PAID
23 u/doublechen-94 PAID
24 u/allidoiswoof PAID
25 u/doublechen-94 PAID
26 u/Jsh0 PAID
27 u/Mission-Swim-8746 PAID
28 u/ThanosWasNotRight PAID
29 u/ThanosWasNotRight PAID
30 u/Txnner PAID
31 u/allidoiswoof PAID
32 u/doublechen-94 PAID
33 u/Jsh0 PAID
34 u/doublechen-94 PAID
35 u/imjakemon PAID
36 u/Be1berhole PAID
37 u/Be1berhole PAID
38 u/Be1berhole PAID
39 u/Be1berhole PAID
40 u/Jsh0 PAID
41 u/doublechen-94 PAID
42 u/SWBGlove PAID
43 u/imjakemon PAID
44 u/GoldToofs15 PAID
45 u/Txnner PAID
46 u/Jsh0 PAID
47 u/doublechen-94 PAID
48 u/SWBGlove PAID
49 u/Ian_thomas22 PAID
50 u/SWBGlove PAID
51 u/allidoiswoof PAID
52 u/allidoiswoof PAID
"""
                
                # Check if current URL matches the test case
                # DISABLED: Manual test data injection disabled to use actual Reddit parsing
                if False and "crown_zenith_pokemon_center_etb_52_spots" in post_url:
                    print("DEBUG: Using manual test allocation data for Crown Zenith raffle")
                    official_allocation = self.parse_official_spot_allocation(manual_allocation_text)
                    print(f"DEBUG: Manual allocation loaded: {len(official_allocation)} users, {sum(len(spots) for spots in official_allocation.values())} spots")
            
            if official_allocation:
                print(f"DEBUG: Total official spots found: {sum(len(spots) for spots in official_allocation.values())}")
            else:
                print("DEBUG: No official allocation found. Using actual Reddit comment parsing only.")

            # Create comment objects for validation
            parsed_comments = []
            for comment_data in basic_post_data["comments"]:
                class CommentObj:
                    def __init__(self, username, spots):
                        self.reddit_username = username
                        self.auto_spots = spots
                
                parsed_comments.append(CommentObj(comment_data["author"], comment_data.get("spots", 0)))

            # Validate the assignments
            validation = self.validate_spot_assignments(parsed_comments, official_allocation)
            
            # Add validation results to the response
            basic_post_data["validation"] = validation
            basic_post_data["official_allocation"] = official_allocation

            # Print validation summary
            if official_allocation:
                print(f"DEBUG: Validation Results:")
                print(f"  - Official spots: {validation['total_official_spots']}")
                print(f"  - Parsed spots: {validation['total_parsed_spots']}")
                print(f"  - Matches: {len(validation['matches'])}")
                print(f"  - Mismatches: {len(validation['mismatches'])}")
                print(f"  - Missing users: {len(validation['missing_users'])}")
                print(f"  - Extra users: {len(validation['extra_users'])}")

                if validation['missing_users']:
                    print("DEBUG: Missing users (should be added):")
                    for missing in validation['missing_users']:
                        print(f"  - {missing['username']}: {missing['official_spots']} spots")
                        
                if validation['mismatches']:
                    print("DEBUG: Mismatches (will be corrected):")
                    for mismatch in validation['mismatches']:
                        print(f"  - {mismatch['username']}: Parsed={mismatch['parsed_spots']} → Official={mismatch['official_spots']}")
            else:
                print("DEBUG: No official allocation found - validation disabled")

            return basic_post_data

        except Exception as e:
            return {"error": f"Failed to fetch post: {str(e)}"}

    def format_timestamp(self, utc_timestamp: float) -> str:
        """Convert UTC timestamp to readable format."""
        dt = datetime.fromtimestamp(utc_timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def is_api_ready(self) -> bool:
        """Check if Reddit API is properly initialized."""
        return self.reddit is not None


# Test function
def test_reddit_parser():
    """Test the Reddit parser with a sample post."""
    parser = RedditParser()
    if not parser.is_api_ready():
        print("Reddit API not ready. Please check config.ini")
        return
    
    # Example URL (replace with actual post URL for testing)
    test_url = "https://www.reddit.com/r/test/comments/example/"
    result = parser.get_post_comments(test_url)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Post: {result['title']}")
        print(f"Author: {result['author']}")
        print(f"Comments found: {len(result['comments'])}")


if __name__ == "__main__":
    test_reddit_parser()