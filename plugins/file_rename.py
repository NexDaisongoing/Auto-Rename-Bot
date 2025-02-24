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

# Global state management
active_rename_tasks = {}
task_processor_lock = asyncio.Lock()

# Episode pattern definitions
EPISODE_PATTERNS = {
    'standard_pattern': re.compile(r'S(\d+)(?:E|EP)(\d+)'),
    'spaced_pattern': re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)'),
    'episode_marker_pattern': re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)'),
    'hyphen_pattern': re.compile(r'(?:\s*-\s*(\d+)\s*)'),
    'season_number_pattern': re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
    'numeric_pattern': re.compile(r'(\d+)')
}

# Quality pattern definitions
QUALITY_PATTERNS = {
    'resolution_pattern': re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE),
    '4k_pattern': re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE),
    '2k_pattern': re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE),
    'hdrip_pattern': re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE),
    '4k_x264_pattern': re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE),
    '4k_x265_pattern': re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)
}

def extract_quality(filename):
    """Extract video quality information from filename."""
    quality_checks = [
        ('resolution_pattern', lambda m: m.group(1) or m.group(2)),
        ('4k_pattern', lambda _: '4k'),
        ('2k_pattern', lambda _: '2k'),
        ('hdrip_pattern', lambda _: 'HdRip'),
        ('4k_x264_pattern', lambda _: '4kX264'),
        ('4k_x265_pattern', lambda _: '4kx265')
    ]

    for pattern_name, quality_extractor in quality_checks:
        match = re.search(QUALITY_PATTERNS[pattern_name], filename)
        if match:
            quality = quality_extractor(match)
            print(f"Matched {pattern_name}")
            print(f"Quality: {quality}")
            return quality

    print("Quality: Unknown")
    return "Unknown"

def extract_episode_number(filename):
    """Extract episode number from filename using multiple patterns."""
    for pattern_name, pattern in EPISODE_PATTERNS.items():
        match = re.search(pattern, filename)
        if match:
            print(f"Matched {pattern_name}")
            return match.group(2) if pattern_name != 'numeric_pattern' else match.group(1)
    return None

async def process_metadata(file_path, new_file_name, file_extension, user_id, status_message):
    """Process file metadata based on file type."""
    metadata_supported_video = {".3g2", ".asf", ".avi", ".drc", ".f4v", ".flv", ".gif", ".gifv", 
                              ".m2ts", ".m4v", ".mkv", ".mov", ".mp4", ".mpe", ".mpeg", ".mpg",
                              ".mpv", ".mxf", ".nsv", ".ogv", ".qt", ".rm", ".rmvb", ".svi",
                              ".ts", ".vob", ".webm", ".wmv", ".yuv"}
    
    metadata_supported_audio = {".3gp", ".aa", ".aac", ".aax", ".act", ".aiff", ".alac", ".amr",
                              ".ape", ".au", ".awb", ".dss", ".dvf", ".flac", ".gsm", ".iklax",
                              ".ivs", ".m4a", ".m4b", ".m4p", ".mmf", ".movpkg", ".mp3", ".mpc",
                              ".msv", ".nmf", ".ogg", ".oga", ".mogg", ".opus", ".ra", ".rm",
                              ".raw", ".rf64", ".sln", ".tta", ".voc", ".vox", ".wav", ".wma",
                              ".wv", ".webm", ".8svx", ".cda"}

    ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
    if not ffmpeg_cmd:
        raise FileNotFoundError("FFmpeg not found. Please install FFmpeg.")

    metadata_output_path = f"Metadata/{new_file_name}"
    os.makedirs(os.path.dirname(metadata_output_path), exist_ok=True)

    if file_extension.lower() in metadata_supported_video:
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
            metadata_output_path
        ]
    elif file_extension.lower() in metadata_supported_audio:
        metadata_command = [
            ffmpeg_cmd,
            '-i', file_path,
            '-metadata', f'title={await madflixbotz.get_atitle(user_id)}',
            '-metadata', f'artist={await madflixbotz.get_aauthor(user_id)}',
            '-metadata', f'genre={await madflixbotz.get_agenre(user_id)}',
            '-metadata', f'album={await madflixbotz.get_aalbum(user_id)}',
            '-map', '0',
            '-c', 'copy',
            '-loglevel', 'error',
            metadata_output_path
        ]
    else:
        await status_message.edit_text("⚠️ Skipping metadata processing for unsupported format")
        return file_path

    process = await asyncio.create_subprocess_exec(
        *metadata_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"Metadata processing failed: {stderr.decode().strip()}")

    await status_message.edit_text("✅ Metadata processing completed")
    return metadata_output_path

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    """Handle automatic file renaming and processing."""
    async with task_processor_lock:
        try:
            status_message = await message.reply_text("🎬 Starting file processing...")
            
            # Extract user information and preferences
            user_id = message.from_user.id
            format_template = await madflixbotz.get_format_template(user_id)
            media_preference = await madflixbotz.get_media_preference(user_id)

            if not format_template:
                await status_message.edit_text("⚠️ No rename format found. Please set format using /autorename")
                return

            # Detect file type and extract information
            await status_message.edit_text("📁 Detecting file type...")
            file_info = {
                'document': (message.document, "📄 Document detected"),
                'video': (message.video, "🎥 Video detected"),
                'audio': (message.audio, "🎵 Audio detected")
            }

            for media_type, (media, detection_message) in file_info.items():
                if getattr(message, media_type):
                    file_id = media.file_id
                    file_name = media.file_name
                    media_type = media_preference or media_type
                    await status_message.edit_text(detection_message)
                    break
            else:
                await status_message.edit_text("❌ Unsupported file type")
                return

            print(f"📋 Processing file: {file_name}")

            # Check if file is already being processed
            if file_id in active_rename_tasks:
                elapsed_time = (datetime.now() - active_rename_tasks[file_id]).seconds
                if elapsed_time < 10:
                    await status_message.edit_text("⏳ File is currently being processed...")
                    return

            active_rename_tasks[file_id] = datetime.now()

            # Extract file information and process
            await status_message.edit_text("🔍 Extracting file information...")
            episode_number = extract_episode_number(file_name)
            print(f"📺 Episode Number: {episode_number}")

            if episode_number:
                for placeholder in ["episode", "Episode", "EPISODE", "{episode}"]:
                    format_template = format_template.replace(placeholder, str(episode_number), 1)
                
                for quality_placeholder in ["quality", "Quality", "QUALITY", "{quality}"]:
                    if quality_placeholder in format_template:
                        extracted_quality = extract_quality(file_name)
                        format_template = format_template.replace(quality_placeholder, 
                                                               "" if extracted_quality == "Unknown" else extracted_quality)

            # Prepare file paths and process file
            file_extension = os.path.splitext(file_name)[1]
            new_file_name = f"{format_template}{file_extension}"
            file_path = f"downloads/{new_file_name}"

            # Download file
            await status_message.edit_text("⬇️ Starting download...")
            try:
                path = await client.download_media(
                    message=message,
                    file_name=file_path,
                    progress=progress_for_pyrogram,
                    progress_args=("Download Started....", status_message, time.time())
                )
            except Exception as e:
                await status_message.edit_text(f"❌ Download failed: {str(e)}")
                del active_rename_tasks[file_id]
                return

            # Extract duration metadata
            duration = 0
            try:
                metadata = extractMetadata(createParser(file_path))
                if metadata.has("duration"):
                    duration = metadata.get('duration').seconds
            except Exception as e:
                print(f"⚠️ Duration extraction error: {e}")

            # Process metadata
            await status_message.edit_text("⬆️ Starting upload...")
            try:
                file_path = await process_metadata(file_path, new_file_name, file_extension, user_id, status_message)
            except Exception as e:
                await status_message.edit_text(f"❌ Metadata Error: {str(e)}")
                return

            # Handle thumbnail
            thumbnail_path = None
            caption_template = await madflixbotz.get_caption(message.chat.id)
            custom_thumbnail = await madflixbotz.get_thumbnail(message.chat.id)

            caption = (caption_template.format(
                filename=new_file_name,
                filesize=humanbytes(message.document.file_size),
                duration=convert(duration)
            ) if caption_template else f"**{new_file_name}**")

            if custom_thumbnail:
                thumbnail_path = await client.download_media(custom_thumbnail)
                print("🖼️ Custom thumbnail applied")
            elif media_type == "video" and message.video.thumbs:
                thumbnail_path = await client.download_media(message.video.thumbs[0].file_id)

            if thumbnail_path:
                img = Image.open(thumbnail_path).convert("RGB")
                img.thumbnail((320, 320))
                img.save(thumbnail_path, "JPEG")

            # Upload processed file
            try:
                upload_methods = {
                    'document': client.send_document,
                    'video': client.send_video,
                    'audio': client.send_audio
                }

                upload_kwargs = {
                    'chat_id': message.chat.id,
                    media_type: file_path,
                    'caption': caption,
                    'thumb': thumbnail_path,
                    'progress': progress_for_pyrogram,
                    'progress_args': ("Upload Started.....", status_message, time.time())
                }

                if media_type in ['video', 'audio']:
                    upload_kwargs['duration'] = duration

                await upload_methods[media_type](**upload_kwargs)
                await status_message.edit_text("✅ File processing completed successfully!")

            except Exception as e:
                await status_message.edit_text(f"❌ Upload failed: {str(e)}")
            finally:
                # Cleanup
                os.remove(file_path)
                if thumbnail_path:
                    os.remove(thumbnail_path)
                del active_rename_tasks[file_id]

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            await message.reply_text(f"❌ An error occurred: {str(e)}")
            if 'file_id' in locals() and file_id in active_rename_tasks:
                del active_rename_tasks[file_id]
