from pyrogram import Client
from config import Config  # Ensure Config.LOG_CHANNEL is defined

async def log_incoming_file(client: Client, message):
    """
    Logs the incoming file by sending a message with user info and forwarding the original message.
    """
    try:
        user = message.from_user
        # Construct a mention with the user's first name and username (if available)
        user_mention = f"[{user.first_name}](tg://user?id={user.id})"
        if user.username:
            user_mention += f" (@{user.username})"
        log_text = f"Incoming file from {user_mention} (ID: {user.id})"
        
        # Send the log message to the log channel
        await client.send_message(Config.LOG_CHANNEL, log_text, parse_mode="md")
        # Forward the original message to the log channel
        await client.forward_messages(Config.LOG_CHANNEL, from_chat_id=message.chat.id, message_ids=message.message_id)
    except Exception as e:
        print(f"Logging error for incoming file: {e}")

async def log_renamed_file(client: Client, original_message, sent_message):
    """
    Logs the renamed (processed) file by sending a log message with user info and forwarding the sent message.
    """
    try:
        user = original_message.from_user
        user_mention = f"[{user.first_name}](tg://user?id={user.id})"
        if user.username:
            user_mention += f" (@{user.username})"
        log_text = f"Renamed file processed for {user_mention} (ID: {user.id})"
        
        await client.send_message(Config.LOG_CHANNEL, log_text, parse_mode="md")
        await client.forward_messages(Config.LOG_CHANNEL, from_chat_id=original_message.chat.id, message_ids=sent_message.message_id)
    except Exception as e:
        print(f"Logging error for renamed file: {e}")
