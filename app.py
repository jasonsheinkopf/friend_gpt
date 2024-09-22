import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from core import FriendGPT
from tools import summarize_chat, get_magic_number

# Load the environment variables
load_dotenv()

models = ['llama3.1:8b', 'gemma2:9b', 'phi3:latest']
tools = [summarize_chat, get_magic_number]
db_path = 'chat_history.db'

# Get the bot token from environment variables
bot_token = os.getenv("DISCORD_TOKEN")

# Define intents
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content in servers
intents.guilds = True
intents.members = True  # Allows handling members

# Initialize the bot with the proper intents
bot = commands.Bot(command_prefix="!", intents=intents)

friend = FriendGPT(models[1], tools, db_path)

# Event: When the bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    friend.name = bot.user.name

# Event: On receiving a message
@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # If it's a message from a server (not DM)
    if message.guild:
        # Say hello to the user in the server
        response = friend.history_tool_chat(message)
        await message.channel.send(response)
    # if its a DM
    else:
        response = friend.history_tool_chat(message)
        await message.author.send(response)
    
    # Ensure other commands are processed
    await bot.process_commands(message)

# A sample command for sending a DM
@bot.command()
async def senddm(ctx, user: discord.User, *, message):
    """Command to send a DM to a specific user."""
    await user.send(message)
    await ctx.send(f"Sent a message to {user.name}.")

# Run the bot with your token
bot.run(bot_token)
