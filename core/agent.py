from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.tools.render import render_text_description
from typing import List
import ollama
import re
import json
from datetime import datetime, timezone
import discord
from core.memory import CoreMemory
from langchain.tools import Tool
import os
import asyncio

# langchain.debug = True


class FriendGPT:
    def __init__(self, tools, cfg):
        self.cfg = cfg
        self.tools = tools
        self.model_name = self.cfg.MODEL
        self.available_models = self.cfg.AVAILABLE_MODELS
        self.tool_names = ", ".join([t.name for t in self.tools])
        self.chat_history = ""
        self.set_prompt_template()
        self.core_memory = None
        self.short_term_memory = None
        self.bot = None
        self.current_channel = None

    def load_identity(self, bot):
        self.name = bot.user.name
        self.id = bot.user.id
        self.bot = bot
        self.core_memory = CoreMemory(self.cfg.CORE_MEMORY_PATH, self.name)
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

        self.prompt_template = '''
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
'''

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

    def get_chat_history(self, message, num_messages):
        '''Retrieves last n messages from channel history'''
        self.chat_history = self.core_memory.get_formatted_chat_history(message.channel.id, self.name, num_messages)

    def find_tool_by_name(self, tools: List[Tool], tool_name: str) -> Tool:
        for t in tools:
            if t.name == tool_name:
                return t
        raise ValueError(f"Tool with name {tool_name} not found")

    def get_token_count(self, result):
        '''Retreive token count from the result and calculate percent fill of context'''
        self.token_counts = {k: v for k, v in result.usage_metadata.items()}
        self.token_counts['context_length'] = self.get_context_length(ollama.show(self.model_name))
        self.token_counts['context_fill'] = int(self.token_counts['total_tokens']) / self.token_counts['context_length']
        for k, v in self.token_counts.items():
            print(f"{k}: {v}")

    async def bot_send_message(self, msg_txt, rec_nick, rec_name, rec_id, chan_id, is_dm, guild_id=''):
        """Send a message to a user or channel."""
        tts = True
        await self.bot.wait_until_ready()  # Ensure the bot is ready before sending messages

        # Define a typing speed (characters per second)
        typing_speed = self.cfg.TYPING_SPEED
        typing_duration = len(msg_txt) / typing_speed  # Calculate how long to "type"

        # If it's a DM channel, send to the user directly
        if is_dm:
            user = await self.bot.fetch_user(rec_id)
            if user:
                dm_channel = await user.create_dm()
                async with dm_channel.typing():  # Show typing indicator in the DM channel
                    await asyncio.sleep(typing_duration)  # Simulate typing based on message length
                    await dm_channel.send(msg_txt, tts=tts)
            else:
                print(f"User with ID {rec_id} not found.")
        # If it's a guild channel send by channel id
        else:
            channel = self.bot.get_channel(chan_id)
            # Check if it's an actual channel
            if channel:
                async with channel.typing():  # Show typing indicator in the guild channel
                    await asyncio.sleep(typing_duration)  # Simulate typing based on message length
                    await channel.send(msg_txt, tts=tts)
            else:
                print(f"Channel with ID {chan_id} not found.")

        # Add the message to the memory
        self.core_memory.add_outgoing_to_memory(msg_txt, rec_nick, rec_name, rec_id, chan_id, guild_id, self.name, 
                                                self.id, self.get_current_utc_datetime(), is_dm
                                                )
        # self.ingest_recent_channel_history(chan_id)
        
    async def ingest_recent_channel_history(self, chan_id):
        '''Check if undigested messages exceed threshold and ingest them to long-term memory'''
        undigested_history = self.core_memory.get_uningested_channel_history(chan_id, chunk_size=10)
        if undigested_history:
            print(f'Ingesting history for channel {chan_id}')
            print(f'Now Ingesting:')
            print(undigested_history)

    async def bot_receive_message(self, message: str):
        self.current_channel = message.channel.id
        self.core_memory.add_incoming_to_memory(message, self.name, self.id, self.get_current_utc_datetime())
        prompt = PromptTemplate.from_template(template=self.prompt_template).partial(
            tools=render_text_description(self.tools),
            tool_names=self.tool_names,
        )

        llm = ChatOllama(model=self.model_name)
        intermediate_steps = ['0. Agent First Thought: Is a tool necessary to respond to the user or not?']
        self.get_chat_history(message, self.cfg.CHAT_HISTORY_LENGTH)

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
                'input': f'{message.author.display_name}: {message.content}',
                'chat_history': self.chat_history,
                'personality': self.personality,
                'agent_scratchpad': "\n".join(intermediate_steps),
                'thought': "0. I'm thinking about what to do next...",
                'last_thought': intermediate_steps[-1],
                'current_model': self.model_name,
                'available_models': self.available_models,
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
                # if tool_return.split()[0].lower() == 'success!':
                #     tool_result = 'The tool was successful. I should not use the tool again. I am ready to respond.'
                # else:
                #     tool_result = 'The tool did not work. I should respond to the user and tell them about the error.'
                # tool_result = tool_return.split('\n')[0]
   
                # if expected response not given, reprompt LLM
                intermediate_steps.append(f'{len(intermediate_steps)}. Agent Thought: {agent_thought}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Used: {tool_name}') 
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Input: {tool_input}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Output: {tool_return}')
                # intermediate_steps.append(f'{len(intermediate_steps)}. Tool Result: {tool_result}')

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
        print(f'\n{message.author.display_name}: "{message.content}"')
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

        # add agent response to memory
        is_dm = True if isinstance(message.channel, discord.DMChannel) == 1 else False
    
        # send message to discord
        await self.bot_send_message(
            msg_txt=final_response,
            rec_nick=message.author.display_name,
            rec_name=message.author.name,
            rec_id=message.author.id,
            chan_id=message.channel.id,
            is_dm=is_dm,
            guild_id='' if is_dm else message.guild.id
        )

