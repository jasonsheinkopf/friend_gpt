import discord
# from discord.ext import commands
import os
from core.agent import FriendGPT
from config.defaults import get_cfg
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Load the configuration
cfg = get_cfg()

# Define intents and initialize
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content in servers
intents.guilds = True
intents.members = True  # Allows handling members
client = discord.Client(intents=intents)

# create an instance of the agent
friend = FriendGPT(cfg)

# Event: When the bot is ready
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    # load identity after bot is ready
    friend.load_identity(client)

# Event: On receiving a message
@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Send the message to FriendGPT for processing
    friend.log_received_message(message)

# Run the bot
try:
    client.run(TOKEN)
except KeyboardInterrupt:
    # Stop the ClockHandler gracefully when Ctrl+C is pressed
    print("Stopping bot gracefully...")
    # clock_handler.stop()
    print("Bot stopped.")