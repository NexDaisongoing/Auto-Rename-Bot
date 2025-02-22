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

# 🛠 Patterns for episode and quality extraction
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')

# 🎥 Conversion Function
async def convert_to_mkv(file_path):
    """Convert MP4, MOV, AVI to MKV format using FFmpeg."""
    try:
        ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
        if not ffmpeg_cmd:
            raise FileNotFoundError("❌ FFmpeg not found. Please install FFmpeg.")
        
        mkv_file_path = file_path.rsplit(".", 1)[0] + ".mkv"
        conversion_command = [
            ffmpeg_cmd, '-i', file_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', mkv_file_path
        ]
        print(f"🔄 Converting {file_path} to {mkv_file_path}...")

        process = await asyncio.create_subprocess_exec(
            *conversion_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            raise RuntimeError(f"❌ Conversion failed: {error_message}")

        print(f"✅ Conversion successful: {mkv_file_path}")
        return mkv_file_path
    except Exception as e:
        print(f"⚠️ Conversion failed: {e}. Using original file.")
        return file_path  # Fallback to original file

# 📌 Auto Rename Handler
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    try:
        user_id = message.from_user.id
        format_template = await madflixbotz.get_format_template(user_id)
        media_preference = await madflixbotz.get_media_preference(user_id)

        if not format_template:
            return await message.reply_text("⚠️ Please set an auto-rename format first using /autorename")

        # 🛠 Determine file details
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
            return await message.reply_text("❌ Unsupported File Type")

        print(f"📂 File received: {file_name}")

        # ⏳ Check if file is already being processed
        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                print("⏳ File is being ignored as it was recently renamed.")
                return
        renaming_operations[file_id] = datetime.now()

        # 🎬 Extract episode number
        episode_number = extract_episode_number(file_name)
        if episode_number:
            format_template = format_template.replace("{episode}", str(episode_number), 1)

        # 📥 Download file
        download_msg = await message.reply_text("📥 Downloading file...")
        file_path = f"downloads/{format_template}{os.path.splitext(file_name)[1]}"
        try:
            path = await client.download_media(message, file_name=file_path)
            print(f"✅ Download completed: {path}")
        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"❌ Download Error: {e}")

        # 🔄 Convert to MKV if needed
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension in [".mp4", ".mov", ".avi"]:
            file_path = await convert_to_mkv(file_path)
            file_extension = ".mkv"

        # 🏷️ Embedding metadata
        metadata_msg = await download_msg.edit("🔧 Embedding metadata...")
        if file_extension in [".mkv", ".avi", ".mov", ".mp4"]:
            try:
                ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
                metadata_file_path = f"Metadata/{format_template}{file_extension}"
                os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

                metadata_command = [
                    ffmpeg_cmd, '-i', file_path,
                    '-metadata', f'title={await madflixbotz.get_title(user_id)}',
                    '-metadata', f'artist={await madflixbotz.get_artist(user_id)}',
                    '-metadata', f'author={await madflixbotz.get_author(user_id)}',
                    '-map', '0', '-c', 'copy', '-loglevel', 'error',
                    metadata_file_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *metadata_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    raise RuntimeError(f"❌ Metadata processing failed: {stderr.decode().strip()}")

                print("✅ Metadata embedding completed.")
                file_path = metadata_file_path
            except Exception as e:
                print(f"⚠️ Metadata embedding failed: {e}")

        # 🚀 Uploading
        upload_msg = await metadata_msg.edit("🚀 Uploading file...")
        try:
            await client.send_document(
                message.chat.id, document=file_path, caption=f"📂 {os.path.basename(file_path)}",
                progress=progress_for_pyrogram, progress_args=("🚀 Upload Started...", upload_msg, time.time())
            )
            print("✅ Upload successful!")
        except Exception as e:
            print(f"❌ Upload error: {e}")

        # 🧹 Cleanup
        os.remove(file_path)
        print("🧹 Cleanup complete.")

        del renaming_operations[file_id]

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
