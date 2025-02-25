from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message 
from PIL import Image
from datetime import datetime
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import madflixbotz
from config import Config
import os
import shutil
import time
import re
import asyncio
import imageio_ffmpeg as ffmpeg

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
    match5 = re.search(pattern5, filename)
    if match5:
        quality5 = match5.group(1) or match5.group(2)
        print("Matched Pattern 5")
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

    unknown_quality = "Unknown"
    print(f"Quality: {unknown_quality}")
    return unknown_quality
    

def extract_episode_number(filename):    
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
        
    return None

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    # Queue the task so that only one file is processed at a time.
    async with processing_lock:
        try:
            status_message = await message.reply_text("🎬 Starting file processing...")
            
            user_id = message.from_user.id
            firstname = message.from_user.first_name
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
                await status_message.edit_text("📄 Document detected")
            elif message.video:
                file_id = message.video.file_id
                file_name = message.video.file_name  # Removed MP4 restriction
                media_type = media_preference or "video"
                await status_message.edit_text("🎥 Video detected")
            elif message.audio:
                file_id = message.audio.file_id
                file_name = message.audio.file_name
                media_type = media_preference or "audio"
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
                            # Remove the placeholder if quality is unknown.
                            format_template = format_template.replace(quality_placeholder, "")
                        else:
                            format_template = format_template.replace(quality_placeholder, extracted_quality)
            
            _, file_extension = os.path.splitext(file_name)
            new_file_name = f"{format_template}{file_extension}. replace("_", " ")
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
            metadata_supported_formats = {".3g2", ".asf", ".avi", ".drc", ".f4v", ".flv", ".gif", ".gifv", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4", ".mpe", ".mpeg", ".mpg", ".mpv", ".mxf", ".nsv", ".ogv", ".qt", ".rm", ".rmvb", ".svi", ".ts", ".vob", ".webm", ".wmv", ".yuv"}
            audio_metadata_formats = {".3gp", ".aa", ".aac", ".aax", ".act", ".aiff", ".alac", ".amr", ".ape", ".au", ".awb", ".dss", ".dvf", ".flac", ".gsm", ".iklax", ".ivs", ".m4a", ".m4b", ".m4p", ".mmf", ".movpkg", ".mp3", ".mpc", ".msv", ".nmf", ".ogg", ".oga", ".mogg", ".opus", ".ra", ".rm", ".raw", ".rf64", ".sln", ".tta", ".voc", ".vox", ".wav", ".wma", ".wv", ".webm", ".8svx", ".cda"}
            
            if file_extension.lower() in metadata_supported_formats:
                try:
                    ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
                    if not ffmpeg_cmd:
                        raise FileNotFoundError("FFmpeg not found. Please install FFmpeg.")

                    metadata_file_path = f"Metadata/{new_file_name.replace'_', ' '}"
                    os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

                    metadata_command = [
                        ffmpeg_cmd,
                        '-i', file_path,
                        '-metadata', f'title={await madflixbotz.get_title(user_id)}',
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
            
            elif file_extension.lower() in audio_metadata_formats:
                try:
                    ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
                    if not ffmpeg_cmd:
                        raise FileNotFoundError("FFmpeg not found. Please install FFmpeg.")

                    metadata_audio_path = f"Metadata/{new_file_name}"
                    os.makedirs(os.path.dirname(metadata_audio_path), exist_ok=True)

                    audio_metadata_command = [
                        ffmpeg_cmd,
                        '-i', file_path,
                        '-metadata', f'title={await madflixbotz.get_atitle(user_id)}',
                        '-metadata', f'artist={await madflixbotz.get_aauthor(user_id)}',
                        '-metadata', f'genre={await madflixbotz.get_agenre(user_id)}',
                        '-metadata', f'album={await madflixbotz.get_aalbum(user_id)}',
                        '-map', '0',
                        '-c', 'copy',
                        '-loglevel', 'error',
                        metadata_audio_path
                    ]

                    process = await asyncio.create_subprocess_exec(
                        *audio_metadata_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()

                    if process.returncode != 0:
                        error_message = stderr.decode().strip()
                        raise RuntimeError(f"Audio metadata processing failed: {error_message}")

                    file_path = metadata_audio_path

                    await status_message.edit_text("✅ Audio metadata processing completed")
                except Exception as e:
                    await status_message.edit_text(f"❌ Audio Metadata Error: {str(e)}")
                    return
            else:
                await status_message.edit_text("⚠️ Skipping metadata processing for unsupported file format")

            ph_path = None
            c_caption = await madflixbotz.get_caption(message.chat.id)
            c_thumb = await madflixbotz.get_thumbnail(message.chat.id)

            caption = (c_caption.format(filename=new_file_name, filesize=humanbytes(message.document.file_size), duration=convert(duration))
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
