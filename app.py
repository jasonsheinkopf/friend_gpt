import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from core.agent import FriendGPT
from config.defaults import get_cfg

import inspect
from langchain.tools import BaseTool
import core.toolbox as toolbox

import asyncio

# Load the environment variables
load_dotenv()

# Get the config from config/defaults.py
cfg = get_cfg()

# Get all the tools from the toolbox for the agent
tools = [member for name, member in inspect.getmembers(toolbox) if isinstance(member, BaseTool)]

# Define intents and initialize
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content in servers
intents.guilds = True
intents.members = True  # Allows handling members
bot = commands.Bot(command_prefix="!", intents=intents)

# create an instance of the agent
friend = FriendGPT(tools, cfg)

# Event: When the bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # load identity after bot is ready
    friend.load_identity(bot)

# Event: On receiving a message
@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process the message with the agent in the background
    asyncio.create_task(friend.bot_receive_message(message))

    # listen for commands
    await bot.process_commands(message)

    # # Always process commands immediately
    # if message.content.startswith(bot.command_prefix):
    # else:
    #     # For non-command messages, process in the background without awaiting
    #     asyncio.create_task(friend.bot_receive_message(message))

# Run the bot with your token
bot.run(os.getenv("DISCORD_TOKEN"))