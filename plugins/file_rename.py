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

renaming_operations = {}

# All your existing patterns remain the same
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

# Your existing extract_quality and extract_episode_number functions remain exactly the same

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    try:
        await message.reply_text("🎬 Starting file processing...")
        
        user_id = message.from_user.id
        firstname = message.from_user.first_name
        format_template = await madflixbotz.get_format_template(user_id)
        media_preference = await madflixbotz.get_media_preference(user_id)

        if not format_template:
            await message.reply_text("⚠️ No rename format found")
            return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

        await message.reply_text("📁 Detecting file type...")
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
            media_type = media_preference or "document"
            await message.reply_text("📄 Document detected")
        elif message.video:
            file_id = message.video.file_id
            file_name = message.video.file_name  # Removed MP4 restriction
            media_type = media_preference or "video"
            await message.reply_text("🎥 Video detected")
        elif message.audio:
            file_id = message.audio.file_id
            file_name = message.audio.file_name
            media_type = media_preference or "audio"
            await message.reply_text("🎵 Audio detected")
        else:
            await message.reply_text("❌ Unsupported file type")
            return

        print(f"📋 Processing file: {file_name}")

        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                await message.reply_text("⏳ File is currently being processed...")
                return

        renaming_operations[file_id] = datetime.now()

        await message.reply_text("🔍 Extracting file information...")
        episode_number = extract_episode_number(file_name)
        print(f"📺 Episode Number: {episode_number}")

        if episode_number:
            placeholders = ["episode", "Episode", "EPISODE", "{episode}"]
            for placeholder in placeholders:
                format_template = format_template.replace(placeholder, str(episode_number), 1)
            
            quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
            for quality_placeholder in quality_placeholders:
                if quality_placeholder in format_template:
                    extracted_qualities = extract_quality(file_name)
                    if extracted_qualities == "Unknown":
                        await message.reply_text("⚠️ Quality extraction failed - using 'Unknown'")
                        del renaming_operations[file_id]
                        return
                    
                    format_template = format_template.replace(quality_placeholder, "".join(extracted_qualities))           
            
        _, file_extension = os.path.splitext(file_name)
        new_file_name = f"{format_template}{file_extension}"
        file_path = f"downloads/{new_file_name}"
        file = message

        download_msg = await message.reply_text("⬇️ Starting download...")
        try:
            path = await client.download_media(
                message=file, 
                file_name=file_path, 
                progress=progress_for_pyrogram, 
                progress_args=("Download Started....", download_msg, time.time())
            )
        except Exception as e:
            del renaming_operations[file_id]
            await message.reply_text(f"❌ Download failed: {str(e)}")
            return await download_msg.edit(e)     

        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata.has("duration"):
                duration = metadata.get('duration').seconds
        except Exception as e:
            print(f"⚠️ Duration extraction error: {e}")

        upload_msg = await download_msg.edit("⬆️ Starting upload...")

        try:
            # Your existing metadata processing code remains the same
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

            await message.reply_text("✅ Metadata processing completed")

        except Exception as e:
            await upload_msg.edit(f"❌ Metadata Error: {str(e)}")
            return

        # Rest of your existing code for thumbnail and upload remains the same
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
            
            await message.reply_text("✅ File processing completed successfully!")
            
        except Exception as e:
            await message.reply_text(f"❌ Upload failed: {str(e)}")
            os.remove(file_path)
            if ph_path:
                os.remove(ph_path)
            return await upload_msg.edit(f"Error: {e}")

        await download_msg.delete() 
        os.remove(file_path)
        if ph_path:
            os.remove(ph_path)

        del renaming_operations[file_id]
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")
        if 'file_id' in locals() and file_id in renaming_operations:
            del renaming_operations[file_id]

# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @Madflix_Bots
# Developer @JishuDeveloper
