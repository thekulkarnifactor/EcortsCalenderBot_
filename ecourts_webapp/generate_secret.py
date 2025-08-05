"""
Script to generate secret.key file for the application.
Run this once after cloning the repository.
"""
import secrets
import os

def generate_secret_key():
    """Generate a secure secret key"""
    secret_key = secrets.token_urlsafe(32)
    
    # Ensure the directory exists
    os.makedirs('ecourts_webapp/data', exist_ok=True)
    
    # Write the secret key
    with open('secret.key', 'w') as f:
        f.write(secret_key)
    
    print("âœ… secret.key generated successfully!")
    print("í´’ This file contains sensitive data and is not tracked by Git.")

if __name__ == "__main__":
    if os.path.exists('secret.key'):
        response = input("secret.key already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("âŒ Operation cancelled.")
            exit()
    
    generate_secret_key()
