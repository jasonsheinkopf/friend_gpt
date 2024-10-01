from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.tools.render import render_text_description
from typing import List
import ollama
import re
import json
from datetime import datetime, timezone
from core.memory import CoreMemory
from langchain.tools import Tool
import os
import asyncio
import inspect
from langchain.tools import BaseTool
import core.toolbox as toolbox
import textwrap
import threading
import time
import queue

# langchain.debug = True


class FriendGPT:
    def __init__(self, cfg):
        self.cfg = cfg
        self.task_queue = queue.Queue()
        self.tools = [member for _, member in inspect.getmembers(toolbox) if isinstance(member, BaseTool)]
        self.tool_names = ", ".join([t.name for t in self.tools])
        self.set_prompt_template()
        self.core_memory = None
        self.short_term_memory = None
        self.bot = None
        self.id = None
        self.name = None
        self.current_channel = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.run_tasks)
        self.running = True  # flag to stop the thread
        self.busy = False  # flag to check if the agent is busy
        self.thread.start()

    def load_identity(self, bot):
        self.name = bot.user.name
        self.id = bot.user.id
        self.bot = bot
        self.core_memory = CoreMemory(self.cfg.CORE_MEMORY_PATH, self.name, self.id)
        # to always use starter personality, set cfg.USE_STARTER_PERSONALITY = True
        if self.cfg.USE_STARTER_PERSONALITY:
            self.personality = self.cfg.STARTER_PERSONALITY.format(discord_bot_username=self.name)
        else:
            # create personality text file from starter if it doesn't exist
            if not os.path.exists(self.cfg.PERSONALITY_PATH):
                with open(self.cfg.PERSONALITY_PATH, 'w') as f:
                    f.write(self.personality)
            with open(self.cfg.PERSONALITY_PATH, 'r') as f:
                self.personality = f.read()

    def set_prompt_template(self):
        self.prompt_template = textwrap.dedent('''\
            You are an agent chatting with friend(s) on Discord with this recent chat history:
            {chat_history}

            Your personality is:
            {personality}

            Your current LLM model is:
            {current_model}

            The LLM models available to you are:
            {available_models}

            Your short-term memory is:
            {short_term_memory}

            You have the following tools available to you to help you respond to only the most recent user message:
            {tools}

            To decide whether to use a tool or simply respond to the user, consider your thought history:
            {agent_scratchpad}

            Reply in the following properly formatted JSON format where all keys and values are strings. Do not include comments:
            {{
                "thought": "In this space, think carefully and write what they are asking for and whether a tool is needed or not. Has a tool already been used successfully?",
                "action": one of "respond, use_tool", # consider your thought '{last_thought}' to decide which action to take
                "tool_name": one of {tool_names},
                "tool_input": "tool input argument matching the tool's docsstring requirements",
                "response": "string response to the user"
            }}

            Most Recent User Input:
            {input}

            Begin!
            ''')

    def get_context_length(self, d):
        if isinstance(d, dict):
            for k, v in d.items():
                if 'context' in k:
                    return v
                elif isinstance(v, dict) or isinstance(v, list):
                    context_length = self.get_context_length(v)
                    if context_length is not None:
                        return context_length

    def get_current_utc_datetime(self):
        # Get the current UTC datetime as a timezone-aware object
        current_utc_time = datetime.now(timezone.utc)
        # Format it as 'YYYY-MM-DD HH:MM:SS'
        return current_utc_time.strftime('%Y-%m-%d %H:%M:%S')

    def load_recent_history(self, channel):
        '''Retrieves last n messages from channel history. Returns long and short history for prompt.'''
        long_history = self.core_memory.get_formatted_chat_history(channel, self.cfg.LONG_HISTORY_LENGTH)
        # Split the chat history into lines
        short_history = long_history.splitlines()
        # Get the last 4 lines
        short_history = short_history[-self.cfg.SHORT_HISTORY_LENGTH:]
        # Join the last 4 lines back into a string
        short_history = "\n".join(short_history)
        return short_history, long_history

    def find_tool_by_name(self, tools: List[Tool], tool_name: str) -> Tool:
        for t in tools:
            if t.name == tool_name:
                return t
        raise ValueError(f"Tool with name {tool_name} not found")

    def get_token_count(self, result):
        '''Retreive token count from the result and calculate percent fill of context'''
        self.token_counts = {k: v for k, v in result.usage_metadata.items()}
        self.token_counts['context_length'] = self.get_context_length(ollama.show(self.cfg.MODEL_NAME))
        self.token_counts['context_fill'] = int(self.token_counts['total_tokens']) / self.token_counts['context_length']
        for k, v in self.token_counts.items():
            print(f"{k}: {v}")

    def send_discord_message(self, channel, msg_txt, typing_duration):
        """Send a message to be sent to a Discord channel."""
        try:
            async def send_message_with_typing():
                async with channel.typing():
                    await asyncio.sleep(typing_duration)
                    await channel.send(msg_txt)
            # schedule coroutine in thread-safe manner
            asyncio.run_coroutine_threadsafe(send_message_with_typing(), self.bot.loop)
        except Exception as e:
            print(f"Failed to send message to channel {channel}: {e}")

    def prepare_and_send_discord_message(self, msg_txt, chan_id):

        # retrieve channel metadata from the first message in the channel
        rec_nick, rec_user, rec_id, guild, is_dm = self.get_channel_metadata(chan_id)

        """Prepare a message to to be send to a user or channel."""
        # await self.bot.wait_until_ready()  # Ensure the bot is ready before sending messages

        # Define a typing speed (characters per second)
        typing_speed = self.cfg.TYPING_SPEED
        typing_duration = len(msg_txt) / typing_speed  # Calculate how long to "type"

        # If it's a DM channel, send to the user directly
        if is_dm:
            try:
                # fetch user and prepare DM channel from received ID
                user = asyncio.run_coroutine_threadsafe(self.bot.fetch_user(rec_id), self.bot.loop).result()
                if user:
                    # get DM channel or create if not available
                    dm_chan_id = user.dm_channel or asyncio.run_coroutine_threadsafe(user.create_dm(), self.bot.loop).result()
                    if dm_chan_id:
                        self.send_discord_message(dm_chan_id, msg_txt, typing_duration)
                    else:
                        print(f"Failed to create DM channel with user {rec_nick}.")
                else:
                    print(f"User with ID {rec_id} not found.")
            except Exception as e:
                print(f"Faile to send message to user {rec_nick}: {e}")
        else:
            try:
                # get the guild channel
                channel = self.bot.get_channel(chan_id)
                if channel:
                    self.send_discord_message(channel, msg_txt, typing_duration)
                else:
                    print(f"Channel with ID {chan_id} not found.")
            except Exception as e:
                print(f"Failed to send message to channel {chan_id}: {e}")

        # Add the message to the memory
        self.core_memory.add_outgoing_to_memory(msg_txt, rec_id, rec_nick, rec_user, is_dm, chan_id, guild, self.get_current_utc_datetime())
        
    # async def ingest_recent_channel_history(self, chan_id):
    #     '''Check if undigested messages exceed threshold and ingest them to long-term memory'''
    #     undigested_history = self.core_memory.get_uningested_channel_history(chan_id, chunk_size=10)
    #     if undigested_history:
    #         print(f'Ingesting history for channel {chan_id}')
    #         print(f'Now Ingesting:')
    #         print(undigested_history)

    def log_received_message(self, message: str):
        '''Log received message to core memory'''
        self.core_memory.add_incoming_to_memory(message, self.get_current_utc_datetime())
        self.current_channel = message.channel.id
        self.add_task(self.reply_to_short_history)

    def add_task(self, task, *args):
        '''Add a task to the task queue'''
        if not args:
            args = ()
        self.task_queue.put((task, args))

    def with_busy_state(func):
        """Decorator to handle setting busy state before and after a task."""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            print(f'Starting task: {func.__name__}')
            print(f'args: {args}')
            print(f'kwargs: {kwargs}')
            # Set busy to True before starting the task
            self.busy = True
            try:
                # Execute the task
                return func(self, *args, **kwargs)
            finally:
                # Set busy to False after task completion
                self.busy = False
        return wrapper

    def run_tasks(self):
        '''Continuous loop to manage and perform the next action'''
        while self.running:
            # Check if the worker is busy; if so, wait briefly
            if self.busy:
                time.sleep(0.1)
                continue

            # If not busy, attempt to get and execute the next action
            try:
                with self.lock:
                    if not self.task_queue.empty():
                        # get next task
                        task, args = self.task_queue.get()
                        # Execute the task with the provided arguments
                        task(*args)
            except Exception as e:
                print(f'Error while starting the next action: {e}')
                self.busy = False

            # Sleep briefly to avoid excessive looping
            time.sleep(0.1)

    def reply_to_short_history(self):
        '''Reply to the most recent messages in the channel'''
        prompt = PromptTemplate.from_template(template=self.prompt_template).partial(
            tools=render_text_description(self.tools),
            tool_names=self.tool_names,
        )

        llm = ChatOllama(model=self.cfg.MODEL)
        intermediate_steps = ['0. Agent First Thought: Is a tool necessary to respond to the user or not?']

        # load recent chat histories
        short_history, long_history = self.load_recent_history(self.current_channel)

        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: x["agent_scratchpad"],
                "chat_history": lambda x: x["chat_history"],
                "personality": lambda x: x["personality"],
                "thought": lambda x: x["thought"],
                "last_thought": lambda x: x["last_thought"],
                "current_model": lambda x: x["current_model"],
                "available_models": lambda x: x["available_models"],
                "short_term_memory": lambda x: x["short_term_memory"],
            }
            | prompt
            | llm
        )

        # Collect prompts and responses for debugging
        interaction_history = []

        action = ""
        while action != "respond":
            prompt_kwargs = {
                'input': short_history,
                'chat_history': long_history,
                'personality': self.personality,
                'agent_scratchpad': "\n".join(intermediate_steps),
                'thought': "0. I'm thinking about what to do next...",
                'last_thought': intermediate_steps[-1],
                'current_model': self.cfg.MODEL_NAME,
                'available_models': self.cfg.AVAILABLE_MODELS,
                'short_term_memory': self.short_term_memory,
            }
            result = agent.invoke(prompt_kwargs)

            try:
                # Regular expression to match the JSON part
                json_pattern = r'\{.*?\}'

                # Extract the JSON string
                match = re.search(json_pattern, result.content, re.DOTALL)

                if match:
                    json_str = match.group(0)
                    response_dict = json.loads(json_str)
                # reprompt LLM if JSON not found
                else:
                    print(f'Error parsing output: {result.content}')
                    continue
            # reprompt LLM if JSON not decodable
            except json.JSONDecodeError:
                print(f'Error parsing output: {result.content}')
                continue
            print('\nModel Output:')
            print(response_dict)

            # add prompt and response to interaction steps for debugging
            interaction_history.append((prompt.format(**prompt_kwargs), response_dict))

            # extract thought
            if 'thought' in response_dict:
                agent_thought = response_dict['thought']
            else:
                agent_thought = 'I am thinking about what to do next...'

            action = response_dict['action']
            # use tool if called
            if response_dict['action'] == 'use_tool':
                if response_dict['tool_name'] not in self.tool_names:
                    continue
                tool_name = response_dict['tool_name']
                tool_to_use = self.find_tool_by_name(self.tools, tool_name)
                tool_input = response_dict['tool_input']
                # call the tool function
                tool_return = tool_to_use.func(agent=self, tool_input=str(tool_input))
   
                # if expected response not given, reprompt LLM
                intermediate_steps.append(f'{len(intermediate_steps)}. Agent Thought: {agent_thought}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Used: {tool_name}') 
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Input: {tool_input}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Output: {tool_return}')

                # print intermediate steps
                print('\nIntermediate Steps:')
                print('\n'.join(intermediate_steps))
            # handle missing response error
            if 'response' in response_dict:
                response = response_dict['response']
            else:
                response = 'Apologies, I am not sure how to respond to that.'
            # add agent response to scratchpad
            final_response = response

        intermediate_steps.append(f'{len(intermediate_steps)}. Agent Final Thought: {agent_thought}')
        intermediate_steps.append(f'{len(intermediate_steps)}. Agent Response: {final_response}')

        # print final response
        print(short_history)
        print(f'{self.name}:\n')
        print('\n'.join(intermediate_steps))

        # save interactions for debugging
        with open('interaction_history.txt', 'w') as f:
            for i, step in enumerate(interaction_history):
                # Pretty-print the dictionary part of the tuple
                pretty_response = json.dumps(step[1], indent=4)
                f.write(f'{"-"*50} LLM call {i + 1} {"-"*50}\n\n')
                f.write(f'*** Prompt to LLM ***\n{step[0]}\n')
                f.write(f'*** Agent Response ***\n\n{pretty_response}\n\n')
                f.write(f'*** Intermediate Steps ***\n\n{"\n".join(intermediate_steps)}\n\n')

        self.prepare_and_send_discord_message(final_response, self.current_channel)
    
    def dummy_action_a(self):
        '''Dummy action that counts to 5 and prints its name'''
        print("Starting Dummy Action A (counting to 5 seconds)...")
        for i in range(5):
            if not self.running:
                print("Stopping Dummy Action A early.")
                return
            print(f"Dummy Action A - Count {i + 1}")
            time.sleep(1)
        print("Finished Dummy Action A.")
        self.busy = False

    def dummy_action_b(self):
        '''Dummy action that counts to 5 and prints its name'''
        print("Starting Dummy Action B (counting to 5 seconds)...")
        for i in range(5):
            if not self.running:
                print("Stopping Dummy Action B early.")
                return
            print(f"Dummy Action B - Count {i + 1}")
            time.sleep(1)
        print("Finished Dummy Action B.")
        self.busy = False

    def stop(self):
        '''Stop the thread and join to finish any remaining tasks'''
        self.running = False
        self.thread.join()