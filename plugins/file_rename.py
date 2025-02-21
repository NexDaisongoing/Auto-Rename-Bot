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

# Patterns for episode and quality extraction
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')

pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)

def extract_quality(filename):
    try:
        match5 = re.search(pattern5, filename)
        if match5:
            print("Matched Pattern 5")
            quality5 = match5.group(1) or match5.group(2)
            print(f"Quality: {quality5}")
            return quality5

        match6 = re.search(pattern6, filename)
        if match6:
            print("Matched Pattern 6")
            quality6 = "4k"
            print(f"Quality: {quality6}")
            return quality6

        match7 = re.search(pattern7, filename)
        if match7:
            print("Matched Pattern 7")
            quality7 = "2k"
            print(f"Quality: {quality7}")
            return quality7

        match8 = re.search(pattern8, filename)
        if match8:
            print("Matched Pattern 8")
            quality8 = "HdRip"
            print(f"Quality: {quality8}")
            return quality8

        match9 = re.search(pattern9, filename)
        if match9:
            print("Matched Pattern 9")
            quality9 = "4kX264"
            print(f"Quality: {quality9}")
            return quality9

        match10 = re.search(pattern10, filename)
        if match10:
            print("Matched Pattern 10")
            quality10 = "4kx265"
            print(f"Quality: {quality10}")
            return quality10    
    except Exception as e:
        print(f"Error extracting quality: {e}")
    unknown_quality = "Unknown"
    print(f"Quality: {unknown_quality}")
    return unknown_quality

def extract_episode_number(filename):    
    try:
        match = re.search(pattern1, filename)
        if match:
            print("Matched Pattern 1")
            return match.group(2)
    
        match = re.search(pattern2, filename)
        if match:
            print("Matched Pattern 2")
            return match.group(2)

        match = re.search(pattern3, filename)
        if match:
            print("Matched Pattern 3")
            return match.group(1)

        match = re.search(pattern3_2, filename)
        if match:
            print("Matched Pattern 3_2")
            return match.group(1)
            
        match = re.search(pattern4, filename)
        if match:
            print("Matched Pattern 4")
            return match.group(2)

        match = re.search(patternX, filename)
        if match:
            print("Matched Pattern X")
            return match.group(1)
    except Exception as e:
        print(f"Error extracting episode number: {e}")
    return None

# Conversion function to convert .mp4, .mov, or .avi to .mkv
async def convert_to_mkv(file_path, new_file_name):
    try:
        ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
        if not ffmpeg_cmd:
            raise FileNotFoundError("FFmpeg not found. Please install FFmpeg.")

        mkv_file_path = file_path.rsplit(".", 1)[0] + ".mkv"
        conversion_command = [
            ffmpeg_cmd,
            '-i', file_path,
            '-map', '0',        # Preserve all streams
            '-c', 'copy',       # Stream copy (no re-encoding)
            '-loglevel', 'error',
            mkv_file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *conversion_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_message = stderr.decode().strip()
            raise RuntimeError(f"Conversion failed: {error_message}")
        print(f"Converted {file_path} to {mkv_file_path}")
        return mkv_file_path
    except Exception as e:
        print(f"Error converting to MKV: {e}")
        return file_path  # Fallback: return the original file if conversion fails

# Example usage for testing:
filename = "Naruto Shippuden S01 - EP07 - 1080p [Dual Audio] @Madflix_Bots.mkv"
episode_number = extract_episode_number(filename)
print(f"Extracted Episode Number: {episode_number}")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    try:
        user_id = message.from_user.id
        firstname = message.from_user.first_name
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
            file_name = f"{message.video.file_name}.mp4"
            media_type = media_preference or "video"
        elif message.audio:
            file_id = message.audio.file_id
            file_name = f"{message.audio.file_name}.mp3"
            media_type = media_preference or "audio"
        else:
            return await message.reply_text("Unsupported File Type")

        print(f"Original File Name: {file_name}")
    
        # Check if file is already being processed
        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                print("File is being ignored as it is currently being renamed or was renamed recently.")
                return
        renaming_operations[file_id] = datetime.now()

        # Extract episode number and update format template
        episode_number = extract_episode_number(file_name)
        print(f"Extracted Episode Number: {episode_number}")
    
        if episode_number:
            for placeholder in ["episode", "Episode", "EPISODE", "{episode}"]:
                format_template = format_template.replace(placeholder, str(episode_number), 1)
            
            for quality_placeholder in ["quality", "Quality", "QUALITY", "{quality}"]:
                if quality_placeholder in format_template:
                    extracted_qualities = extract_quality(file_name)
                    if extracted_qualities == "Unknown":
                        await message.reply_text("I Was Not Able To Extract The Quality Properly. Renaming As 'Unknown'...")
                        del renaming_operations[file_id]
                        return
                    format_template = format_template.replace(quality_placeholder, "".join(extracted_qualities))
    
        # Build new file name and path
        _, file_extension = os.path.splitext(file_name)
        new_file_name = f"{format_template}{file_extension}"
        file_path = f"downloads/{new_file_name}"

        # Download the media file
        download_msg = await message.reply_text(text="Trying To Download.....")
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

        # If file is mp4, mov, or avi, convert to mkv
        if file_extension.lower() in [".mp4", ".mov", ".avi"]:
            try:
                file_path = await convert_to_mkv(file_path, new_file_name)
                file_extension = ".mkv"
            except Exception as e:
                print(f"Conversion error: {e}")

        upload_msg = await download_msg.edit("Trying To Uploading.....")

        # If file format supports metadata embedding, run the metadata command
        if file_extension.lower() in [".mkv", ".avi", ".mov", ".mp4"]:
            try:
                ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
                if not ffmpeg_cmd:
                    raise FileNotFoundError("FFmpeg not found. Please install FFmpeg.")

                metadata_file_path = f"Metadata/{new_file_name}"
                os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

                metadata_command = [
                    ffmpeg_cmd,
                    '-i', file_path,
                    '-metadata', f'title={await madflixbotz.get_title(user_id)}',
                    '-metadata', f'artist={await madflixbotz.get_artist(user_id)}',
                    '-metadata', f'author={await madflixbotz.get_author(user_id)}',
                    '-metadata:s:v', f'title={await madflixbotz.get_video(user_id)}',
                    '-metadata:s:a', f'title={await madflixbotz.get_audio(user_id)}',
                    '-metadata:s:s', f'title={await madflixbotz.get_subtitle(user_id)}',
                    '-map', '0',
                    '-c', 'copy',
                    '-loglevel', 'error',
                    metadata_file_path
                ]

                process = await asyncio.create_subprocess_exec(
                    *metadata_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    error_message = stderr.decode().strip()
                    raise RuntimeError(f"Metadata processing failed: {error_message}")
                # Use the metadata-embedded file for upload
                file_path = metadata_file_path

            except FileNotFoundError as e:
                await upload_msg.edit(f"**Error:** {str(e)}")
                return
            except RuntimeError as e:
                await upload_msg.edit(f"**Metadata Error:** {str(e)}")
                return
            except Exception as e:
                await upload_msg.edit(f"**Unexpected Error (metadata):** {str(e)}")
                return
        else:
            print("File format not supported for metadata embedding. Skipping metadata step.")

        # Download and process thumbnail if available
        ph_path = None
        try:
            c_caption = await madflixbotz.get_caption(message.chat.id)
            c_thumb = await madflixbotz.get_thumbnail(message.chat.id)
            caption = (c_caption.format(filename=new_file_name, filesize=humanbytes(message.document.file_size), duration=convert(duration))
                       if c_caption else f"**{new_file_name}**")
            if c_thumb:
                ph_path = await client.download_media(c_thumb)
                print(f"Thumbnail downloaded successfully. Path: {ph_path}")
            elif media_type == "video" and message.video.thumbs:
                ph_path = await client.download_media(message.video.thumbs[0].file_id)
            if ph_path:
                try:
                    img = Image.open(ph_path).convert("RGB")
                    img = img.resize((320, 320))
                    img.save(ph_path, "JPEG")
                except Exception as thumb_e:
                    print(f"Thumbnail processing error: {thumb_e}")
                    ph_path = None
        except Exception as e:
            print(f"Error handling thumbnail: {e}")
            caption = f"**{new_file_name}**"

        # Upload file based on media type
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=file_path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", upload_msg, time.time())
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", upload_msg, time.time())
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", upload_msg, time.time())
                )
        except Exception as e:
            try:
                os.remove(file_path)
                if ph_path:
                    os.remove(ph_path)
            except Exception as remove_e:
                print(f"Error during cleanup: {remove_e}")
            return await upload_msg.edit(f"Upload Error: {e}")

        # Cleanup downloaded files
        try:
            await download_msg.delete()
            os.remove(file_path)
            if ph_path:
                os.remove(ph_path)
        except Exception as cleanup_e:
            print(f"Cleanup error: {cleanup_e}")

        del renaming_operations[file_id]

    except Exception as outer_e:
        print(f"Unexpected error in auto_rename_files: {outer_e}")
