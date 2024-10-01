import discord
import threading
import time
import queue
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# ClockHandler class that runs in a separate thread
class ClockHandler:
    def __init__(self, bot_client):
        self.task_queue = queue.Queue()
        self.lock = threading.Lock()
        self.running = True
        self.bot_client = bot_client
        # Start the thread without daemon, as you want explicit control over stopping
        self.thread = threading.Thread(target=self.run_tasks)
        self.thread.start()

    def add_message(self, message):
        # Add message processing task to the queue
        self.task_queue.put(message)

    def run_tasks(self):
        while self.running:
            try:
                # Get the next message from the queue with a timeout to allow graceful shutdown
                message = self.task_queue.get(timeout=1)
                # Lock to ensure only one message is processed at a time
                with self.lock:
                    if self.running:  # Double-check if still running before processing
                        self.bot_client.loop.call_soon_threadsafe(self.process_message, message)
            except queue.Empty:
                # No messages to process, continue to check if the thread should stop
                continue

    def process_message(self, message):
        # Simulate processing the message by running a clock for 30 seconds
        print(f"Processing message: {message.content}")
        for _ in range(30):  # Looping to check `self.running` periodically during long sleep
            if not self.running:
                print("Stopping processing early.")
                return
            time.sleep(1)
        
        print("Finished processing message.")
        
        # Send a message back to the Discord channel
        asyncio.run_coroutine_threadsafe(
            message.channel.send(f"Finished processing your message: {message.content}"), 
            self.bot_client.loop
        )

    def stop(self):
        # Gracefully stop the thread
        self.running = False
        # Join to make sure the thread finishes any remaining task
        self.thread.join()

# Discord bot client
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Create an instance of ClockHandler
clock_handler = ClockHandler(client)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Add the message to the ClockHandler queue for processing
    clock_handler.add_message(message)

# Run the bot
try:
    client.run(TOKEN)
except KeyboardInterrupt:
    # Stop the ClockHandler gracefully when Ctrl+C is pressed
    print("Stopping bot gracefully...")
    clock_handler.stop()
    print("Bot stopped.")
