
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message, InlineKeyboardMarkup, InlineKeyboardButton
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

# -----------------------------
# Global Variables & Constants
# -----------------------------

processing_lock = asyncio.Lock()
renaming_operations: Dict[str, datetime] = {}

# New globals for queue management
processing_queue = []  # List of file processing jobs (each is a dict)
queue_message = None   # Message that displays the dynamic queue status
abort_all = False      # Flag to abort all operations
queue_processing_task = None  # Task for processing the queue

# Precompile regex patterns
PATTERNS = {
    # Episode patterns
    'pattern1': re.compile(r'S(\d+)(?:E|EP)(\d+)'),
    'pattern2': re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)'),
    'pattern3': re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)'),
    'pattern3_2': re.compile(r'(?:\s*-\s*(\d+)\s*)'),
    'pattern4': re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
    'patternX': re.compile(r'(\d+)'),
    # Quality patterns
    'pattern5': re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE),
    'pattern6': re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE),
    'pattern7': re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE),
    'pattern8': re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE),
    'pattern9': re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE),
    'pattern10': re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)
}

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

FFMPEG_PATH = "ffmpeg"  # Modify this if ffmpeg is in a specific location

# ------------------------------------
# Original LRU Cache Utility Functions
# ------------------------------------

@functools.lru_cache(maxsize=128)
def extract_quality(filename: str) -> str:
    """Extract quality from filename with LRU caching for repeated patterns."""
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

@functools.lru_cache(maxsize=128)
def extract_episode_number(filename: str) -> Optional[str]:
    """Extract episode number from filename with LRU caching."""
    for pattern_name in ('pattern1', 'pattern2', 'pattern3', 'pattern3_2', 'pattern4', 'patternX'):
        match = re.search(PATTERNS[pattern_name], filename)
        if match:
            if pattern_name in ('pattern1', 'pattern2', 'pattern4'):
                return match.group(2)
            return match.group(1)
    return None

# -------------------------------
# Original Helper Functions
# -------------------------------

async def get_file_info(message: Message) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract file information from message."""
    if message.document:
        return message.document.file_id, message.document.file_name, "document"
    elif message.video:
        return message.video.file_id, message.video.file_name, "video"
    elif message.audio:
        return message.audio.file_id, message.audio.file_name, "audio"
    return None, None, None

async def process_metadata(file_path: str, new_file_name: str, file_ext: str, user_id: int) -> Optional[str]:
    """Process metadata for supported file formats using ffmpeg subprocess."""
    metadata_path = None
    try:
        metadata_dir = f"Metadata"
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = f"{metadata_dir}/{new_file_name}"

        if file_ext.lower() in METADATA_SUPPORTED_FORMATS:
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

# -----------------------------
# New Queue & Progress Features
# -----------------------------

async def update_queue_message(client, chat_id: int):
    """
    Updates (or creates) the queue message showing:
    - Pending files: 🔄 [OG] file_name (old name)
    - Processing files: progress indicator (e.g., ⬤◯◯) with live logs
    - Completed files: ✅ [OG] file_name with [RN] new name
    - Failed files: ❌ file_name with error reason
    An "Abort All Operations" button is appended if files remain.
    """
    global queue_message
    text = "📥 Files Added to Queue:\n"
    for item in processing_queue:
        status = item.get("status", "pending")
        original_name = item.get("original_name", "Unknown")
        display_line = ""
        if status == "pending":
            display_line = f"🔄 [OG] {original_name} (old name)"
        elif status == "processing":
            progress = item.get("progress", "◯◯◯")
            display_line = f"{progress} [OG] {original_name} (processing)"
            if "log" in item:
                display_line += f"\n    └─ Log: {item['log']}"
        elif status == "completed":
            new_name = item.get("new_name", "")
            display_line = f"✅ [OG] {original_name}"
            if new_name:
                display_line += f"\n    └─ [RN] {new_name}"
        elif status == "failed":
            error_reason = item.get("error_reason", "Unknown error")
            display_line = f"❌ {original_name}\n    └─ (Reason: {error_reason})"
        text += display_line + "\n"
    # Append abort button if there are files in queue and not aborted
    if processing_queue and not abort_all:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Abort All Operations", callback_data="abort_all")]]
        )
    else:
        keyboard = None
    if queue_message:
        try:
            await client.edit_message_text(chat_id, queue_message.message_id, text, reply_markup=keyboard)
        except Exception:
            pass
    else:
        queue_message = await client.send_message(chat_id, text, reply_markup=keyboard)

async def process_file(client, queue_item):
    """
    Processes a single file from the queue.
    Implements live progress updates, error handling with a 30-second delay,
    and displays a completion tick with the new name upon success.
    """
    global abort_all
    file_message = queue_item["message"]
    chat_id = file_message.chat.id
    file_id = queue_item["file_id"]
    original_name = queue_item["original_name"]

    # Mark as processing and update queue display
    queue_item["status"] = "processing"
    queue_item["progress"] = "◯◯◯"
    await update_queue_message(client, chat_id)

    status_message = None
    file_path = None
    ph_path = None

    try:
        status_message = await file_message.reply_text("🎬 Starting file processing...")

        # Get user info and settings
        user_id = file_message.from_user.id
        format_template = await madflixbotz.get_format_template(user_id)
        media_preference = await madflixbotz.get_media_preference(user_id)

        if not format_template:
            await status_message.edit_text("⚠️ No rename format found. Please Set An Auto Rename Format First Using /autorename")
            queue_item["status"] = "failed"
            queue_item["error_reason"] = "No rename format set"
            await update_queue_message(client, chat_id)
            return

        # Detect file type
        await status_message.edit_text("📁 Detecting file type...")
        fid, fname, ftype = await get_file_info(file_message)
        if not all([fid, fname, ftype]):
            await status_message.edit_text("❌ Unsupported file type")
            queue_item["status"] = "failed"
            queue_item["error_reason"] = "Unsupported file type"
            await update_queue_message(client, chat_id)
            return

        media_type = media_preference or ftype
        await status_message.edit_text(f"{'📄 Document' if ftype == 'document' else '🎥 Video' if ftype == 'video' else '🎵 Audio'} detected")

        # Avoid duplicate processing
        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                await status_message.edit_text("⏳ File is currently being processed...")
                return
        renaming_operations[file_id] = datetime.now()

        # Extract file information and generate new filename
        await status_message.edit_text("🔍 Extracting file information...")
        episode_number = extract_episode_number(fname)
        format_template_copy = format_template
        if episode_number:
            for placeholder in ["episode", "Episode", "EPISODE", "{episode}"]:
                format_template_copy = format_template_copy.replace(placeholder, str(episode_number), 1)
            for quality_placeholder in ["quality", "Quality", "QUALITY", "{quality}"]:
                if quality_placeholder in format_template_copy:
                    extracted_quality = extract_quality(fname)
                    if extracted_quality == "Unknown":
                        format_template_copy = format_template_copy.replace(quality_placeholder, "")
                    else:
                        format_template_copy = format_template_copy.replace(quality_placeholder, extracted_quality)

        _, file_extension = os.path.splitext(fname)
        new_file_name = f"{format_template_copy}{file_extension}"
        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        file_path = f"{downloads_dir}/{new_file_name}"

        # Download file
        await status_message.edit_text("⬇️ Starting download...")
        try:
            path = await client.download_media(
                message=file_message,
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=("Download Started....", status_message, time.time())
            )
        except Exception as e:
            await status_message.edit_text(f"❌ Download failed: {str(e)}")
            queue_item["status"] = "failed"
            queue_item["error_reason"] = f"Download failed: {str(e)}"
            await update_queue_message(client, chat_id)
            await asyncio.sleep(30)
            return

        # Live processing progress simulation (updating dot indicators)
        for progress in ["◯◯◯", "⬤◯◯", "⬤⬤◯", "⬤⬤⬤"]:
            if abort_all:
                raise asyncio.CancelledError("Aborted by user")
            queue_item["progress"] = progress
            queue_item["log"] = "Extracting metadata..."
            await update_queue_message(client, chat_id)
            await asyncio.sleep(1)

        # Extract duration (if possible)
        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata and metadata.has("duration"):
                duration = metadata.get('duration').seconds
        except Exception:
            pass

        await status_message.edit_text("⬆️ Starting upload...")

        # Process metadata if format is supported
        if file_extension.lower() in METADATA_SUPPORTED_FORMATS or file_extension.lower() in AUDIO_METADATA_FORMATS:
            try:
                metadata_path = await process_metadata(file_path, new_file_name, file_extension, user_id)
                if metadata_path:
                    file_path = metadata_path
                    await status_message.edit_text("✅ Metadata processing completed")
                else:
                    await status_message.edit_text("⚠️ Skipping metadata processing for unsupported file format")
            except Exception as e:
                await status_message.edit_text(f"❌ Metadata Error: {str(e)}")
                queue_item["status"] = "failed"
                queue_item["error_reason"] = f"Metadata Error: {str(e)}"
                await update_queue_message(client, chat_id)
                await asyncio.sleep(30)
                return
        else:
            await status_message.edit_text("⚠️ Skipping metadata processing for unsupported file format")

        # Permanently rename file
        desired_path = os.path.join(os.path.dirname(file_path), new_file_name)
        try:
            os.rename(file_path, desired_path)
            file_path = desired_path
        except OSError as e:
            raise RuntimeError(f"Error occurred while renaming file from {file_path} to {desired_path}: {e}")

        # Process thumbnail
        c_caption = await madflixbotz.get_caption(chat_id)
        c_thumb = await madflixbotz.get_thumbnail(chat_id)

        try:
            file_size = getattr(file_message.document, 'file_size', 
                        getattr(file_message.video, 'file_size', 
                        getattr(file_message.audio, 'file_size', 0)))
        except AttributeError:
            file_size = 0

        caption = (c_caption.format(
            filename=new_file_name,
            filesize=humanbytes(file_size), 
            duration=convert(duration))
            if c_caption else f"**{new_file_name}**")

        if c_thumb:
            ph_path = await client.download_media(c_thumb)
        elif media_type == "video" and file_message.video and file_message.video.thumbs and len(file_message.video.thumbs) > 0:
            ph_path = await client.download_media(file_message.video.thumbs[0].file_id)

        if ph_path:
            with Image.open(ph_path) as img:
                img = img.convert("RGB").resize((320, 320))
                img.save(ph_path, "JPEG", optimize=True)

        # Upload the processed file
        try:
            if media_type == "document":
                await client.send_document(
                    chat_id,
                    document=file_path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", status_message, time.time())
                )
            elif media_type == "video":
                await client.send_video(
                    chat_id,
                    video=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", status_message, time.time())
                )
            elif media_type == "audio":
                await client.send_audio(
                    chat_id,
                    audio=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started.....", status_message, time.time())
                )

            await status_message.edit_text("✅ File processing completed successfully!")
            queue_item["status"] = "completed"
            queue_item["new_name"] = new_file_name
            await update_queue_message(client, chat_id)
        except Exception as e:
            await status_message.edit_text(f"❌ Upload failed: {str(e)}")
            queue_item["status"] = "failed"
            queue_item["error_reason"] = f"Upload failed: {str(e)}"
            await update_queue_message(client, chat_id)
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        await file_message.reply_text("⚠️ File processing aborted.")
        queue_item["status"] = "failed"
        queue_item["error_reason"] = "Aborted by user"
        await update_queue_message(client, chat_id)
    except Exception as e:
        if status_message:
            await status_message.edit_text(f"❌ An error occurred: {str(e)}")
        else:
            await file_message.reply_text(f"❌ An error occurred: {str(e)}")
        queue_item["status"] = "failed"
        queue_item["error_reason"] = str(e)
        await update_queue_message(client, chat_id)
        await asyncio.sleep(30)
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        if file_id in renaming_operations:
            del renaming_operations[file_id]

async def process_queue(client, chat_id: int):
    """
    Processes the files in the queue sequentially.
    If abort_all is triggered, marks remaining files as aborted,
    updates the queue display and then deletes the queue message.
    """
    global processing_queue, abort_all, queue_processing_task
    while processing_queue:
        if abort_all:
            for item in processing_queue:
                item["status"] = "failed"
                item["error_reason"] = "Aborted by user"
            await update_queue_message(client, chat_id)
            break
        current_item = processing_queue.pop(0)
        await process_file(client, current_item)
    # Delete the queue message after processing all files or after abort
    if queue_message:
        try:
            await client.delete_messages(chat_id, [queue_message.message_id])
        except Exception:
            pass
    abort_all = False
    queue_processing_task = None

# -----------------------------
# Abort All Operations Handler
# -----------------------------

@Client.on_callback_query(filters.regex("^abort_all$"))
async def abort_all_callback(client, callback_query):
    """
    When the user clicks the "Abort All Operations" button,
    immediately stop the current processing, clear pending files,
    remove temporary downloads and update the queue message.
    """
    global abort_all, processing_queue, queue_processing_task
    abort_all = True
    await callback_query.answer("Aborting all operations...", show_alert=True)
    processing_queue.clear()
    await update_queue_message(client, callback_query.message.chat.id)
    if queue_processing_task:
        queue_processing_task.cancel()

# -----------------------------
# Modified on_message Handler
# -----------------------------

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    """
    Instead of processing immediately, this handler adds the incoming file
    to the processing queue (with its original name and a pending indicator)
    and then starts the queue processor if not already running.
    """
    global processing_queue, queue_processing_task
    file_id, file_name, file_type = await get_file_info(message)
    if not file_id:
        await message.reply_text("❌ Unsupported file type")
        return
    queue_item = {
        "message": message,
        "file_id": file_id,
        "original_name": file_name,
        "status": "pending",
        "progress": "🔄"
    }
    processing_queue.append(queue_item)
    await update_queue_message(client, message.chat.id)
    if not queue_processing_task:
        queue_processing_task = asyncio.create_task(process_queue(client, message.chat.id))