#!/usr/bin/env python3
import os
import subprocess
import sys

def find_ffmpeg_path():
    """Find the path to FFmpeg executable on a Linux system."""
    try:
        # Try using 'which' on Linux
        result = subprocess.run(['which', 'ffmpeg'], 
                              capture_output=True, 
                              text=True, 
                              check=False)
        
        if result.returncode == 0:
            # Return the first path if multiple are found
            return result.stdout.strip().split('\n')[0]
        else:
            # If the command failed, try common Linux locations
            common_locations = [
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/opt/ffmpeg/bin/ffmpeg",
                "/snap/bin/ffmpeg"
            ]
            
            for location in common_locations:
                if os.path.isfile(location):
                    return location
            
            return None
    except Exception as e:
        print(f"Error while searching for FFmpeg: {e}", file=sys.stderr)
        return None

# For Telegram bot integration
def handle_path_command(update, context):
    """Handler for the /path command in a Telegram bot."""
    ffmpeg_path = find_ffmpeg_path()
    if ffmpeg_path:
        message = f"FFmpeg found at: {ffmpeg_path}"
    else:
        message = "FFmpeg not found on this system. Please make sure it's installed."
    
    # Send message back to user
    update.message.reply_text(message)

# You can integrate this with your Telegram bot like this:
'''
from telegram.ext import CommandHandler

def setup_handlers(dispatcher):
    # Add command handler for /path
    dispatcher.add_handler(CommandHandler("path", handle_path_command))
'''

# Standalone testing
if __name__ == "__main__":
    ffmpeg_path = find_ffmpeg_path()
    if ffmpeg_path:
        print(f"FFmpeg found at: {ffmpeg_path}")
    else:
        print("FFmpeg not found on this system. Please make sure it's installed."
