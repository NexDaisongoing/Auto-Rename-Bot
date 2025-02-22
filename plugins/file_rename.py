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
import imageio_ffmpeg as ffmpeg
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis

# Global lock for processing queue
processing_lock = asyncio.Lock()
renaming_operations = {}

# Pattern definitions remain unchanged...
# Pattern 1: S01E02 or S01EP02
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
# Pattern 2: S01 E02 or S01 EP02 or S01 - E01 or S01 - EP02
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
# Pattern 3: Episode Number After "E" or "EP"
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
# Pattern 3_2: episode number after - [hyphen]
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
# Pattern 4: S2 09 ex.
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
# Pattern X: Standalone Episode Number
patternX = re.compile(r'(\d+)')
# QUALITY PATTERNS 
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)

def extract_quality(filename):
    for pattern, quality in [
        (pattern5, lambda match: match.group(1) or match.group(2)),
        (pattern6, "4k"),
        (pattern7, "2k"),
        (pattern8, "HdRip"),
        (pattern9, "4kX264"),
        (pattern10, "4kx265")
    ]:
        match = re.search(pattern, filename)
        if match:
            print(f"Matched Pattern {pattern}")
            return quality(match) if callable(quality) else quality
    return "Unknown"

def extract_episode_number(filename):    
    for pattern in [pattern1, pattern2, pattern3, pattern3_2, pattern4, patternX]:
        match = re.search(pattern, filename)
        if match:
            print(f"Matched Pattern {pattern}")
            return match.group(2) if pattern in [pattern1, pattern2, pattern4] else match.group(1)
    return None

async def process_file_with_timeout(file_id, task, timeout=30):
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        print(f"⏳ Timeout occurred for file {file_id}, skipping...")
        if file_id in renaming_operations:
            del renaming_operations[file_id]

async def update_audio_metadata(file_path, metadata):
    if file_path.endswith('.mp3'):
        audio = EasyID3(file_path)
    elif file_path.endswith('.m4a'):
        audio = MP4(file_path)
    elif file_path.endswith('.flac'):
        audio = FLAC(file_path)
    elif file_path.endswith('.ogg'):
        audio = OggVorbis(file_path)
    else:
        return False

    for key, value in metadata.items():
        audio[key] = value
    audio.save()
    return True

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    async with processing_lock:
        try:
            status_message = await message.reply_text("🎬 Starting file processing...")
            
            user_id = message.from_user.id
            format_template = await madflixbotz.get_format_template(user_id)
            media_preference = await madflixbotz.get_media_preference(user_id)

            if not format_template:
                await status_message.edit_text("⚠️ No rename format found. Please Set An Auto Rename Format First Using /autorename")
                return

            await status_message.edit_text("📁 Detecting file type...")
            if message.document:
                file_id = message.document.file_id
                file_name = message.document.file_name
                media_type = media_preference or "document"
                file_size = message.document.file_size
                await status_message.edit_text("📄 Document detected")
            elif message.video:
                file_id = message.video.file_id
                file_name = message.video.file_name
                media_type = media_preference or "video"
                file_size = message.video.file_size
                await status_message.edit_text("🎥 Video detected")
            elif message.audio:
                file_id = message.audio.file_id
                file_name = message.audio.file_name
                media_type = media_preference or "audio"
                file_size = message.audio.file_size
                await status_message.edit_text("🎵 Audio detected")
            else:
                await status_message.edit_text("❌ Unsupported file type")
                return

            print(f"📋 Processing file: {file_name}")

            if file_id in renaming_operations:
                elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
                if elapsed_time < 10:
                    await status_message.edit_text("⏳ File is currently being processed...")
                    return

            renaming_operations[file_id] = datetime.now()

            await status_message.edit_text("🔍 Extracting file information...")
            episode_number = extract_episode_number(file_name)
            print(f"📺 Episode Number: {episode_number}")

            if episode_number:
                placeholders = ["episode", "Episode", "EPISODE", "{episode}"]
                for placeholder in placeholders:
                    format_template = format_template.replace(placeholder, str(episode_number), 1)
                
                quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
                for quality_placeholder in quality_placeholders:
                    if quality_placeholder in format_template:
                        extracted_quality = extract_quality(file_name)
                        if extracted_quality == "Unknown":
                            format_template = format_template.replace(quality_placeholder, "")
                        else:
                            format_template = format_template.replace(quality_placeholder, extracted_quality)
            
            _, file_extension = os.path.splitext(file_name)
            new_file_name = f"{format_template}{file_extension}"
            file_path = f"downloads/{new_file_name}"
            file = message

            await status_message.edit_text("⬇️ Starting download...")
            try:
                path = await client.download_media(
                    message=file, 
                    file_name=file_path, 
                    progress=progress_for_pyrogram, 
                    progress_args=("Download Started....", status_message, time.time())
                )
            except Exception as e:
                await status_message.edit_text(f"❌ Download failed: {str(e)}")
                del renaming_operations[file_id]
                return

            duration = 0
            try:
                metadata = extractMetadata(createParser(file_path))
                if metadata.has("duration"):
                    duration = metadata.get('duration').seconds
            except Exception as e:
                print(f"⚠️ Duration extraction error: {e}")

            await status_message.edit_text("⬆️ Starting upload...")

            # Check if the file format supports metadata embedding
            metadata_supported_formats = {".mkv", ".avi", ".mov", ".mp4"}
            if file_extension.lower() in metadata_supported_formats:
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

                    file_path = metadata_file_path

                    await status_message.edit_text("✅ Metadata processing completed")
                except Exception as e:
                    await status_message.edit_text(f"❌ Metadata Error: {str(e)}")
                    return
            else:
                await status_message.edit_text("⚠️ Skipping metadata processing for unsupported file format")

            ph_path = None
            c_caption = await madflixbotz.get_caption(message.chat.id)
            c_thumb = await madflixbotz.get_thumbnail(message.chat.id)

            caption = (c_caption.format(filename=new_file_name, filesize=humanbytes(file_size), duration=convert(duration))
                       if c_caption else f"**{new_file_name}**")

            if c_thumb:
                ph_path = await client.download_media(c_thumb)
                print("🖼️ Custom thumbnail applied")
            elif media_type == "video" and message.video.thumbs:
                ph_path = await client.download_media(message.video.thumbs[0].file_id)

            if ph_path:
                Image.open(ph_path).convert("RGB").save(ph_path)
                img = Image.open(ph_path)
                img = img.resize((320, 320))
                img.save(ph_path, "JPEG")    
            
            try:
                if media_type == "document":
                    await client.send_document(
                        message.chat.id,
                        document=file_path,
                        thumb=ph_path,
                        caption=caption,
                        progress=progress_for_pyrogram,
                        progress_args=("Upload Started.....", status_message, time.time())
                    )
                elif media_type == "video":
                    await client.send_video(
                        message.chat.id,
                        video=file_path,
                        caption=caption,
                        thumb=ph_path,
                        duration=duration,
                        progress=progress_for_pyrogram,
                        progress_args=("Upload Started.....", status_message, time.time())
                    )
                elif media_type == "audio":
                    await client.send_audio(
                        message.chat.id,
                        audio=file_path,
                        caption=caption,
                        thumb=ph_path,
                        duration=duration,
                        progress=progress_for_pyrogram,
                        progress_args=("Upload Started.....", status_message, time.time())
                    )
                
                await status_message.edit_text("✅ File processing completed successfully!")
                
            except Exception as e:
                await status_message.edit_text(f"❌ Upload failed: {str(e)}")
                os.remove(file_path)
                if ph_path:
                    os.remove(ph_path)
                return

            os.remove(file_path)
            if ph_path:
                os.remove(ph_path)

            del renaming_operations[file_id]
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            await message.reply_text(f"❌ An error occurred: {str(e)}")
            if 'file_id' in locals() and file_id in renaming_operations:
                del renaming_operations[file_id]

@Client.on_message(filters.command("setaudioinfo"))
async def set_audio_info(client, message):
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: /setaudioinfo <artist> <title> <genre> <album>")
            return

        user_id = message.from_user.id
        artist, title, genre, album = message.command[1:5]

        await madflixbotz.set_audio_info(user_id, artist, title, genre, album)
        await message.reply_text("✅ Audio metadata updated successfully!")
    except Exception as e:
        await message.reply_text(f"❌ Error updating audio metadata: {str(e)}")

@Client.on_message(filters.command("applyaudioinfo"))
async def apply_audio_info(client, message):
    try:
        user_id = message.from_user.id
        audio_info = await madflixbotz.get_audio_info(user_id)

        if not audio_info:
            await message.reply_text("⚠️ No audio metadata found. Please set audio metadata first using /setaudioinfo.")
            return

        if not message.reply_to_message or not message.reply_to_message.audio:
            await message.reply_text("⚠️ Please reply to an audio file to apply metadata.")
            return

        file_id = message.reply_to_message.audio.file_id
        file_name = message.reply_to_message.audio.file_name
        file_path = f"downloads/{file_name}"

        await message.reply_text("⬇️ Downloading audio file...")
        await client.download_media(message=message.reply_to_message, file_name=file_path)

        await message.reply_text("🔧 Applying audio metadata...")
        if await update_audio_metadata(file_path, audio_info):
            await message.reply_text("✅ Audio metadata applied successfully!")
        else:
            await message.reply_text("❌ Unsupported audio format for metadata editing.")

        os.remove(file_path)
    except Exception as e:
        await message.reply_text(f"❌ Error applying audio metadata: {str(e)}")
