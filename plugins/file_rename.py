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
import subprocess
import functools
from typing import Dict, Optional, Tuple, Set
from collections import deque

# Improved global variables
processing_lock = asyncio.Lock()
renaming_operations: Dict[str, datetime] = {}

# Global queue and state variables
queue = deque()
queue_message: Optional[Message] = None
abort_flag = False
processing_task = None

# Precompile regex patterns once
PATTERNS = {
    # Episode patterns
    'pattern1': re.compile(r'S(\d+)(?:E|EP)(\d+)'),
    'pattern2': re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)'),
    'pattern3': re.compile(r'(?:[([ ])?)'),
    'pattern3_2': re.compile(r'(?:\s*-\s*(\d+)\s*)'),
    'pattern4': re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
    'patternX': re.compile(r'(\d+)'),
    # Quality patterns
    'pattern5': re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE),
    'pattern6': re.compile(r'[([ ])?', re.IGNORECASE),
    'pattern7': re.compile(r'[([ ])?', re.IGNORECASE),
    'pattern8': re.compile(r'[([ })]?|\bHdRip\b', re.IGNORECASE),
    'pattern9': re.compile(r'[([ ])?', re.IGNORECASE),
    'pattern10': re.compile(r'[([ ])?', re.IGNORECASE)
}

# Predefine constants
METADATA_SUPPORTED_FORMATS: Set[str] = {
    ".3g2", ".asf", ".avi", ".drc", ".f4v", ".flv", ".gif", ".gifv", ".m2ts", ".m4v", 
    ".mkv", ".mov", ".mp4", ".mpe", ".mpeg", ".mpg", ".mpv", ".mxf", ".nsv", ".ogv", 
    ".qt", ".rm", ".rmvb", ".svi", ".ts", ".vob", ".webm", ".wmv", ".yuv"
}

AUDIO_METADATA_FORMATS: Set[str] = {
    ".3gp", ".aa", ".aac", ".aax", ".act", ".aiff", ".alac", ".amr", ".ape", ".au", 
    ".awb", ".dss", ".dvf", ".flac", ".gsm", ".iklax", ".ivs", ".m4a", ".m4b", ".m4p", 
    ".mmf", ".movpkg", ".mp3", ".mpc", ".msv", ".nmf", ".ogg", ".oga", ".mogg", ".opus", 
    ".ra", ".rm", ".raw", ".rf64", ".sln", ".tta", ".voc", ".vox", ".wav", ".wma", ".wv", 
    ".webm", ".8svx", ".cda"
}

# Path to ffmpeg v4.4 executable
FFMPEG_PATH = "ffmpeg"  # Modify this if ffmpeg is in a specific location

# LRU cache for quality extraction
@functools.lru_cache(maxsize=128)
def extract_quality(filename: str) -> str:
    """Extract quality from filename with LRU caching for repeated patterns."""
    # Try each pattern in order
    for pattern_name in ('pattern5', 'pattern6', 'pattern7', 'pattern8', 'pattern9', 'pattern10'):
        match = re.search(PATTERNS[pattern_name], filename)
        if match:
            if pattern_name == 'pattern5':
                return match.group(1) or match.group(2)
            elif pattern_name == 'pattern6':
                return "4k" 
            elif pattern_name == 'pattern7':
                return "2k"
            elif pattern_name == 'pattern8':
                return "HdRip"
            elif pattern_name == 'pattern9':
                return "4kX264"
            elif pattern_name == 'pattern10':
                return "4kx265"

    return "Unknown"

# LRU cache for episode extraction
@functools.lru_cache(maxsize=128)
def extract_episode_number(filename: str) -> Optional[str]:
    """Extract episode number from filename with LRU caching."""
    # Try each pattern in order
    for pattern_name in ('pattern1', 'pattern2', 'pattern3', 'pattern3_2', 'pattern4', 'patternX'):
        match = re.search(PATTERNS[pattern_name], filename)
        if match:
            # For patterns 1, 2, and 4, we want group 2
            if pattern_name in ('pattern1', 'pattern2', 'pattern4'):
                return match.group(2)
            # For other patterns we want group 1
            return match.group(1)

    return None

# Helper function to get file type and info
async def get_file_info(message: Message) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract file information from message."""
    if message.document:
        return message.document.file_id, message.document.file_name, "document"
    elif message.video:
        return message.video.file_id, message.video.file_name, "video"
    elif message.audio:
        return message.audio.file_id, message.audio.file_name, "audio"
    return None, None, None

# Process metadata with optimized function using subprocess
async def process_metadata(file_path: str, new_file_name: str, file_ext: str, user_id: int) -> Optional[str]:
    """Process metadata for supported file formats using ffmpeg v4.4 subprocess."""
    metadata_path = None

    try:
        metadata_dir = f"Metadata"
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = f"{metadata_dir}/{new_file_name}"

        if file_ext.lower() in METADATA_SUPPORTED_FORMATS:
            # Video metadata
            metadata_command = [
                FFMPEG_PATH,
                '-i', file_path,
                '-metadata', f'title={await madflixbotz.get_title(user_id)}',
                '-metadata:s:v', f'title={await madflixbotz.get_video(user_id)}',
                '-metadata:s:a', f'title={await madflixbotz.get_audio(user_id)}',
                '-metadata:s:s', f'title={await madflixbotz.get_subtitle(user_id)}',
                '-map', '0',
                '-c', 'copy',
                '-loglevel', 'error',
                metadata_path
            ]
        elif file_ext.lower() in AUDIO_METADATA_FORMATS:
            # Audio metadata
            metadata_command = [
                FFMPEG_PATH,
                '-i', file_path,
                '-metadata', f'title={await madflixbotz.get_atitle(user_id)}',
                '-metadata', f'artist={await madflixbotz.get_aauthor(user_id)}',
                '-metadata', f'genre={await madflixbotz.get_agenre(user_id)}',
                '-metadata', f'album={await madflixbotz.get_aalbum(user_id)}',
                '-map', '0',
                '-c', 'copy',
                '-loglevel', 'error',
                metadata_path
            ]
        else:
            return None

        process = await asyncio.create_subprocess_exec(
            *metadata_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            raise RuntimeError(f"Metadata processing failed: {error_message}")

        return metadata_path

    except Exception as e:
        if metadata_path and os.path.exists(metadata_path):
            os.remove(metadata_path)
        raise e

# New helper functions for queue management
async def update_queue_message():
    global queue_message
    status_lines = []
    for file_info in queue:
        status = file_info.get('status', '🔄')
        orig_name = file_info.get('orig_name', '')
        new_name = file_info.get('new_name', '')
        progress = file_info.get('progress', '◯◯◯')
        error = file_info.get('error', '')
        
        line = f"{status} [OG] {orig_name}"
        if 'completed' in file_info:
            line += f"\n └─ [RN] {new_name}"
        elif error:
            line += f"\n └─ (Reason: {error})"
        else:
            line += f" {progress}"
        status_lines.append(line)
    
    if abort_flag:
        text = "⚠️ All file operations have been aborted by the user.\n(Queue cleared)"
        if queue_message:
            await queue_message.edit(text)
            queue_message = None
        return
    
    text = "📥 Files Added to Queue:\n"
    text += "\n".join(status_lines)
    if not abort_flag:
        text += "\n\n❌ Abort All Operations"
    
    if queue_message:
        await queue_message.edit(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abort All Operations", callback_data="abort_all")]]))
    else:
        queue_message = await queue[0]['message'].reply(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abort All Operations", callback_data="abort_all")]]))

async def reset_queue():
    global queue, queue_message, abort_flag
    queue = deque()
    if queue_message:
        await queue_message.delete()
        queue_message = None
    abort_flag = False

async def process_queue():
    global processing_task
    while queue:
        if abort_flag:
            break
        file_info = queue.popleft()
        await process_file(file_info)
        await asyncio.sleep(1)
    await reset_queue()

async def process_file(file_info):
    global abort_flag
    try:
        file_info['status'] = '🔄'
        await update_queue_message()
        await asyncio.sleep(1)  # Simulate initial processing delay
        
        # Get user information
        user_id = file_info['message'].from_user.id
        format_template = await madflixbotz.get_format_template(user_id)
        media_preference = await madflixbotz.get_media_preference(user_id)

        if not format_template:
            file_info['status'] = '❌'
            file_info['error'] = "No rename format found. Please Set An Auto Rename Format First Using /autorename"
            await update_queue_message()
            return

        # Extract file information
        file_id, file_name, file_type = await get_file_info(file_info['message'])

        if not all([file_id, file_name, file_type]):
            file_info['status'] = '❌'
            file_info['error'] = "Unsupported file type"
            await update_queue_message()
            return

        media_type = media_preference or file_type

        # Check if file is already being processed
        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                file_info['status'] = '❌'
                file_info['error'] = "File is currently being processed..."
                await update_queue_message()
                return

        renaming_operations[file_id] = datetime.now()

        # Process filename
        await file_info['message'].edit_text("🔍 Extracting file information...")
        episode_number = extract_episode_number(file_name)

        # Apply format template replacements
        format_template_copy = format_template
        if episode_number:
            # Replace episode placeholders
            for placeholder in ["episode", "Episode", "EPISODE", "{episode}"]:
                format_template_copy = format_template_copy.replace(placeholder, str(episode_number), 1)

            # Replace quality placeholders
            for quality_placeholder in ["quality", "Quality", "QUALITY", "{quality}"]:
                if quality_placeholder in format_template_copy:
                    extracted_quality = extract_quality(file_name)
                    if extracted_quality == "Unknown":
                        format_template_copy = format_template_copy.replace(quality_placeholder, "")
                    else:
                        format_template_copy = format_template_copy.replace(quality_placeholder, extracted_quality)

        # Create new filename
        _, file_extension = os.path.splitext(file_name)
        new_file_name = f"{format_template_copy}{file_extension}"
        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        file_path = f"{downloads_dir}/{new_file_name}"

        # Download file
        await file_info['message'].edit_text("⬇️ Starting download...")
        try:
            path = await client.download_media(
                message=file_info['message'],
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=("Download Started....", file_info['message'], time.time())
            )
        except Exception as e:
            file_info['status'] = '❌'
            file_info['error'] = f"Download failed: {str(e)}"
            await update_queue_message()
            del renaming_operations[file_id]
            return

        # Extract duration
        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata and metadata.has("duration"):
                duration = metadata.get('duration').seconds
        except Exception:
            pass

        await file_info['message'].edit_text("⬆️ Starting upload...")

        # Process metadata if supported
        if file_extension.lower() in METADATA_SUPPORTED_FORMATS or file_extension.lower() in AUDIO_METADATA_FORMATS:
            try:
                metadata_path = await process_metadata(file_path, new_file_name, file_extension, user_id)
                if metadata_path:
                    file_path = metadata_path
                    file_info['progress'] = '⬤⬤⬤'
                    file_info['status'] = '🔄'
                    await update_queue_message()
                    await asyncio.sleep(1)
                else:
                    file_info['progress'] = '⬤⬤⬤'
                    file_info['status'] = '🔄'
                    file_info['error'] = "Skipping metadata processing for unsupported file format"
                    await update_queue_message()
                    await asyncio.sleep(1)
            except Exception as e:
                file_info['status'] = '❌'
                file_info['error'] = f"Metadata Error: {str(e)}"
                await update_queue_message()
                return
        else:
            file_info['progress'] = '⬤⬤⬤'
            file_info['status'] = '🔄'
            file_info['error'] = "Skipping metadata processing for unsupported file format"
            await update_queue_message()
            await asyncio.sleep(1)

        # Permanently rename the file using os.rename if the basename does not match the auto-rename format.
        desired_path = os.path.join(os.path.dirname(file_path), new_file_name)
        try:
            os.rename(file_path, desired_path)
            file_path = desired_path  # Update file_path to the new location
        except OSError as e:
            file_info['status'] = '❌'
            file_info['error'] = f"Error occurred while renaming file from {file_path} to {desired_path}: {e}"
            await update_queue_message()
            return

        # Process thumbnail
        c_caption = await madflixbotz.get_caption(file_info['message'].chat.id)
        c_thumb = await madflixbotz.get_thumbnail(file_info['message'].chat.id)

        try:
            file_size = getattr(file_info['message'].document, 'file_size', 
                        getattr(file_info['message'].video, 'file_size', 
                        getattr(file_info['message'].audio, 'file_size', 0)))
        except AttributeError: 
            file_size = 0  # Default to 0 if no file_size attribute is found

        caption = (c_caption.format(
            filename=new_file_name,
            filesize=humanbytes(file_size), 
            duration=convert(duration))
            if c_caption else f"**{new_file_name}**")

        if c_thumb:
            ph_path = await client.download_media(c_thumb)
        elif media_type == "video" and file_info['message'].video and file_info['message'].video.thumbs and len(file_info['message'].video.thumbs) > 0:
            ph_path = await client.download_media(file_info['message'].video.thumbs[0].file_id)

        if ph_path:
            # Optimize image processing
            with Image.open(ph_path) as img:
                img = img.convert("RGB").resize((320, 320))
                img.save(ph_path, "JPEG", optimize=True)

        # Upload processed file
        try:
            if media_type == "document":
                await client.send_document(
                    file_info['message'].chat.id,
                    document=file_path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", file_info['message'], time.time())
                )
            elif media_type == "video":
                await client.send_video(
                    file_info['message'].chat.id,
                    video=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", file_info['message'], time.time())
                )
            elif media_type == "audio":
                await client.send_audio(
                    file_info['message'].chat.id,
                    audio=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", file_info['message'], time.time())
                )

            file_info['status'] = '✅'
            file_info['completed'] = True
            file_info['new_name'] = new_file_name
            await update_queue_message()
            await file_info['message'].edit_text("✅ File processing completed successfully!")

        except Exception as e:
            file_info['status'] = '❌'
            file_info['error'] = f"Upload failed: {str(e)}"
            await update_queue_message()
            return

    except Exception as e:
        file_info['status'] = '❌'
        file_info['error'] = f"An error occurred: {str(e)}"
        await update_queue_message()

    finally:
        # Clean up
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        if file_id in renaming_operations:
            del renaming_operations[file_id]

# Callback handler for abort button
@Client.on_callback_query(filters.regex("abort_all"))
async def abort_all_callback(client, callback_query):
    global abort_flag
    if not abort_flag:
        abort_flag = True
        await update_queue_message()
        # Cleanup temporary files
        try:
            if os.path.exists("downloads"):
                shutil.rmtree("downloads")
            if os.path.exists("Metadata"):
                shutil.rmtree("Metadata")
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
        await callback_query.answer("All operations aborted", show_alert=True)
        await reset_queue()

# Modified auto_rename_files function to handle queue
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    global queue, processing_task
    # Add file to queue with original name and message reference
    queue.append({
        'orig_name': message.document.file_name if message.document else message.video.file_name,
        'message': message,
        'status': '🔄',
        'progress': '◯◯◯'
    })
    
    # Start processing if not already running
    if not processing_task or processing_task.done():
        processing_task = asyncio.create_task(process_queue())
    
    # Update queue message
    await update_queue_message()