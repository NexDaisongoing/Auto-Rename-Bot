from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message
from PIL import Image
from datetime import datetime
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import madflixbotz
from config import Config
import os
import shutil
import time
import re
import asyncio
import imageio_ffmpeg as ffmpeg  # To reliably obtain the FFmpeg executable

renaming_operations = {}

# Regex patterns for episode and quality extraction (same as before)
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')

pattern5 = re.compile(r'\b(?:.?(\d{3,4}[^\dp]p).?|.?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s4k\s[)]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s2k\s[)]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\sHdRip\s[)]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s4kX264\s[)]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s4kx265\s[)]>}]?', re.IGNORECASE)

def extract_quality(filename):
    try:
        match5 = re.search(pattern5, filename)
        if match5:
            return match5.group(1) or match5.group(2)

        match6 = re.search(pattern6, filename)
        if match6:
            return "4k"

        match7 = re.search(pattern7, filename)
        if match7:
            return "2k"

        match8 = re.search(pattern8, filename)
        if match8:
            return "HdRip"

        match9 = re.search(pattern9, filename)
        if match9:
            return "4kX264"

        match10 = re.search(pattern10, filename)
        if match10:
            return "4kx265"

    except Exception as e:
        print(f"Error extracting quality: {e}")

    return "Unknown"

def extract_episode_number(filename):
    try:
        match = re.search(pattern1, filename)
        if match:
            return match.group(2)

        match = re.search(pattern2, filename)
        if match:
            return match.group(2)

        match = re.search(pattern3, filename)
        if match:
            return match.group(1)

        match = re.search(pattern3_2, filename)
        if match:
            return match.group(1)

        match = re.search(pattern4, filename)
        if match:
            return match.group(2)

        match = re.search(patternX, filename)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error extracting episode number: {e}")
    return None

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    try:
        user_id = message.from_user.id
        format_template = await madflixbotz.get_format_template(user_id)
        media_preference = await madflixbotz.get_media_preference(user_id)

        if not format_template:
            return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

        # Determine file details  
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
            media_type = media_preference or "document"
        elif message.video:
            file_id = message.video.file_id
            file_name = message.video.file_name  # ✅ Change: Now keeps the original format
            media_type = media_preference or "video"
        elif message.audio:
            file_id = message.audio.file_id
            file_name = f"{message.audio.file_name}.mp3"
            media_type = media_preference or "audio"
        else:
            return await message.reply_text("Unsupported File Type")

        print(f"Original File Name: {file_name}")

        # Prevent multiple renaming attempts on the same file
        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                return

        renaming_operations[file_id] = datetime.now()

        # Extract episode number and update format template
        episode_number = extract_episode_number(file_name)
        if episode_number:
            format_template = format_template.replace("{episode}", str(episode_number), 1)

        # Extract quality and update format template
        extracted_quality = extract_quality(file_name)
        format_template = format_template.replace("{quality}", extracted_quality)

        # Generate new file path
        _, file_extension = os.path.splitext(file_name)
        new_file_name = f"{format_template}{file_extension}"
        file_path = f"downloads/{new_file_name}"

        # Download the file
        download_msg = await message.reply_text("Trying To Download.....")
        try:
            path = await client.download_media(
                message=message,
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=("Download Started....", download_msg, time.time())
            )
        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"Download Error: {e}")

        # Extract duration using hachoir
        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata and metadata.has("duration"):
                duration = metadata.get('duration').seconds
        except Exception as e:
            print(f"Error getting duration: {e}")

        upload_msg = await download_msg.edit("Trying To Uploading.....")

        # Upload file based on media type
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=file_path,
                    caption=f"**{new_file_name}**",
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", upload_msg, time.time())
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=file_path,
                    caption=f"**{new_file_name}**",
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", upload_msg, time.time())
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=file_path,
                    caption=f"**{new_file_name}**",
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", upload_msg, time.time())
                )
        except Exception as e:
            try:
                os.remove(file_path)
            except Exception as remove_e:
                print(f"Error during cleanup: {remove_e}")
            return await upload_msg.edit(f"Upload Error: {e}")

        # Cleanup downloaded files
        try:
            await download_msg.delete()
            os.remove(file_path)
        except Exception as cleanup_e:
            print(f"Cleanup error: {cleanup_e}")

        del renaming_operations[file_id]

    except Exception as outer_e:
        print(f"Unexpected error in auto_rename_files: {outer_e}")
