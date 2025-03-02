import os
import subprocess
import sys
from pyrogram import Client, filters

def find_ffmpeg_path():
    """Find the path to FFmpeg executable on a Linux system."""
    try:
        # Try using 'which' on Linux
        result = subprocess.run(['which', 'ffmpeg'], 
                                capture_output=True, 
                                text=True, 
                                check=False)
        
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
        else:
            # Check common Linux locations
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
        return f"Error while searching for FFmpeg: {e}"

@Client.on_message(filters.command("path"))
async def handle_path_command(client, message):
    """Handler for the /path command in a Pyrogram bot."""
    ffmpeg_path = find_ffmpeg_path()
    if ffmpeg_path:
        response = f"✅ FFmpeg found at:\n`{ffmpeg_path}`"
    else:
        response = "❌ FFmpeg not found on this system.\nPlease install it using:\n`sudo apt install ffmpeg`"
    
    await message.reply_text(response)
