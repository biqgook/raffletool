"""
Data management module for handling user database operations.
"""

import pandas as pd
import os
from typing import List, Dict, Optional


class UserDatabase:
    def __init__(self, database_file: str = "data/user_database.xlsx"):
        """Initialize user database manager."""
        self.database_file = database_file
        self.df = None
        self.load_database()

    def load_database(self):
        """Load user database from Excel file."""
        if os.path.exists(self.database_file):
            try:
                self.df = pd.read_excel(self.database_file)
                # Ensure required columns exist
                required_columns = ['Reddit_Username', 'PayPal_Name', 'Discord_Name']
                for col in required_columns:
                    if col not in self.df.columns:
                        if col == 'PayPal_Name' and 'PayPal Name' in self.df.columns:
                            self.df.rename(columns={'PayPal Name': 'PayPal_Name'}, inplace=True)
                        else:
                            self.df[col] = ''
                print(f"Database loaded: {len(self.df)} users")
            except Exception as e:
                print(f"Error loading database: {e}")
                self.create_empty_database()
        else:
            self.create_empty_database()

    def create_empty_database(self):
        """Create an empty database with required columns."""
        self.df = pd.DataFrame(columns=['Reddit_Username', 'PayPal_Name', 'Discord_Name'])
        print("Created new empty database")

    def save_database(self):
        """Save user database to Excel file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.database_file), exist_ok=True)
            self.df.to_excel(self.database_file, index=False)
            print(f"Database saved to {self.database_file}")
            return True
        except Exception as e:
            print(f"Error saving database: {e}")
            return False

    def add_user(self, reddit_username: str, paypal_name: str = "", discord_name: str = "") -> bool:
        """Add a new user to the database."""
        # Check if user already exists
        if self.user_exists(reddit_username):
            print(f"User {reddit_username} already exists")
            return False
        
        new_row = pd.DataFrame({
            'Reddit_Username': [reddit_username],
            'PayPal_Name': [paypal_name],
            'Discord_Name': [discord_name]
        })
        
        self.df = pd.concat([self.df, new_row], ignore_index=True)
        print(f"Added user: {reddit_username}")
        return True

    def update_user(self, reddit_username: str, paypal_name: str = None, discord_name: str = None) -> bool:
        """Update an existing user's information."""
        user_index = self.df[self.df['Reddit_Username'] == reddit_username].index
        
        if len(user_index) == 0:
            print(f"User {reddit_username} not found")
            return False
        
        idx = user_index[0]
        if paypal_name is not None:
            self.df.loc[idx, 'PayPal_Name'] = paypal_name
        if discord_name is not None:
            self.df.loc[idx, 'Discord_Name'] = discord_name
        
        print(f"Updated user: {reddit_username}")
        return True

    def delete_user(self, reddit_username: str) -> bool:
        """Delete a user from the database."""
        initial_length = len(self.df)
        self.df = self.df[self.df['Reddit_Username'] != reddit_username]
        
        if len(self.df) < initial_length:
            print(f"Deleted user: {reddit_username}")
            return True
        else:
            print(f"User {reddit_username} not found")
            return False

    def search_user(self, reddit_username: str) -> Optional[Dict]:
        """Search for a user by Reddit username."""
        user_row = self.df[self.df['Reddit_Username'] == reddit_username]
        
        if len(user_row) > 0:
            return user_row.iloc[0].to_dict()
        return None

    def user_exists(self, reddit_username: str) -> bool:
        """Check if a user exists in the database."""
        return len(self.df[self.df['Reddit_Username'] == reddit_username]) > 0

    def get_all_users(self) -> List[Dict]:
        """Get all users as a list of dictionaries."""
        return self.df.to_dict('records')

    def get_user_count(self) -> int:
        """Get total number of users in database."""
        return len(self.df)

    def search_by_paypal(self, paypal_name: str) -> Optional[Dict]:
        """Search for a user by PayPal name."""
        user_row = self.df[self.df['PayPal_Name'].str.contains(paypal_name, case=False, na=False)]
        
        if len(user_row) > 0:
            return user_row.iloc[0].to_dict()
        return None

    def search_by_discord(self, discord_name: str) -> Optional[Dict]:
        """Search for a user by Discord name."""
        user_row = self.df[self.df['Discord_Name'].str.contains(discord_name, case=False, na=False)]
        
        if len(user_row) > 0:
            return user_row.iloc[0].to_dict()
        return None

    def export_to_excel(self, filename: str) -> bool:
        """Export database to a different Excel file."""
        try:
            self.df.to_excel(filename, index=False)
            print(f"Database exported to {filename}")
            return True
        except Exception as e:
            print(f"Error exporting database: {e}")
            return False

    def import_from_excel(self, filename: str) -> bool:
        """Import database from Excel file."""
        try:
            new_df = pd.read_excel(filename)
            # Validate columns
            required_columns = ['Reddit_Username']
            if not all(col in new_df.columns for col in required_columns):
                print("Invalid Excel file format. Must contain Reddit_Username column.")
                return False
            
            self.df = new_df
            self.save_database()
            print(f"Database imported from {filename}")
            return True
        except Exception as e:
            print(f"Error importing database: {e}")
            return False


# Test function
def test_user_database():
    """Test the user database functionality."""
    db = UserDatabase("test_database.xlsx")
    
    # Test adding users
    db.add_user("testuser1", "Test User 1", "testuser1#1234")
    db.add_user("testuser2", "Test User 2", "testuser2#5678")
    
    # Test searching
    user = db.search_user("testuser1")
    print(f"Found user: {user}")
    
    # Test updating
    db.update_user("testuser1", discord_name="newtestuser1#1234")
    
    # Test saving
    db.save_database()
    
    print(f"Total users: {db.get_user_count()}")


if __name__ == "__main__":
    test_user_database()