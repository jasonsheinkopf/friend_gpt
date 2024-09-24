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
        self.core_memory = CoreMemory(cfg.CORE_MEMORY_PATH)

    def load_identity(self, name, id):
        self.name = name
        self.id = id
        self.personality = self.cfg.PERSONALITY.format(discord_bot_username=name)

    def set_prompt_template(self):

        self.prompt_template = '''
You are an agent chatting with friend(s) on Discord with this recent chat history:

{chat_history}.

Your personality is:

{personality}.

Your current LLM model is:

{current_model}

The LLM models available to you are:

{available_models}

You have the following tools available to you. You can use these tools to help you respond to the user:

{tools}

To decide whether to use a tool or simply respond to the user, consider your thought history:

{agent_scratchpad}.

Reply in the following properly formatted JSON format where all keys and values are strings:

{{
    "thought": "Write your thoughts about what you should do here. Include whether a tool has already been used.",
    "action": one of "respond, use_tool", # consider your last thought {last_thought}
    "tool_name": one of {tool_names},
    "tool_input": "tool input argument matching the tool's docsstring requirements",
    "response": "string response to the user"
}}

User Input: {input}

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

    def get_chat_history(self, message, num_messages=100):
        '''Retrieves last n messages from channel history'''
        is_dm = True if isinstance(message.channel, discord.DMChannel) == 1 else False
        guild_id = None if is_dm else message.guild.id
        self.chat_history = self.core_memory.get_formatted_chat_history(message.channel.id, guild_id, self.name, is_dm, num_messages)

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

    def reply_to_message(self, message: str):
        self.core_memory.add_incoming_to_memory(message, self.name, self.id, self.get_current_utc_datetime())
        prompt = PromptTemplate.from_template(template=self.prompt_template).partial(
            tools=render_text_description(self.tools),
            tool_names=self.tool_names,
        )

        llm = ChatOllama(model=self.model_name)
        intermediate_steps = ['a careful thought about what you want to do']
        self.get_chat_history(message)

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
            }
            | prompt
            | llm
        )

        action = ""
        while action != "respond":
            result = agent.invoke(
                {
                    "input": message.content,
                    "chat_history": self.chat_history,
                    "personality": self.personality,
                    "agent_scratchpad": intermediate_steps,
                    "thought": "0. I'm thinking about what to do next...",
                    "last_thought": intermediate_steps[-1],
                    "current_model": self.model_name,
                    "available_models": self.available_models,
                }
            )

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

            print('Model replied with:')
            print(response_dict)

            action = response_dict['action']

            # use tool if called
            if response_dict['action'] == 'use_tool':
                if response_dict['tool_name'] not in self.tool_names:
                    continue
                tool_name = response_dict['tool_name']
                tool_to_use = self.find_tool_by_name(self.tools, tool_name)
                tool_input = response_dict['tool_input']
                # call the tool function
                observation = tool_to_use.func(agent=self, tool_input=str(tool_input))
                if observation.split()[0].lower() == 'success!':
                    tool_result = 'The tool was successful. I should not use the tool again. I am ready to respond.'
                else:
                    tool_result = 'The tool did not work. I should respond to the user and tell them about the error.'
   
                # add tool output to scratchpad
                intermediate_steps.append(f'{len(intermediate_steps)}. Agent Thought: {response_dict["thought"]}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Used: {tool_name}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Input: {tool_input}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Tool Output: {observation}')
                intermediate_steps.append(f'{len(intermediate_steps)}. Post Tool Thought: {tool_result}')

                # print intermediate steps
                print('\n'.join(intermediate_steps))

        # add agent response to scratchpad
        agent_thought = response_dict['thought']
        final_response = response_dict['response']
        intermediate_steps.append(f'{len(intermediate_steps)}. Agent Final Thought: {agent_thought}')
        intermediate_steps.append(f'{len(intermediate_steps)}. Agent Response: {final_response}')

        # print final response
        print('\n'.join(intermediate_steps))

        # add agent response to memory
        is_dm = True if isinstance(message.channel, discord.DMChannel) == 1 else False
        self.core_memory.add_outgoing_to_memory(
            out_message_content=final_response,
            recipient_display_name=message.author.display_name,
            recipient_name=message.author.name,
            recipient_id=message.author.id,
            channel_id=message.channel.id,
            guild_id='' if is_dm else message.guild.id,
            bot_name=self.name,
            bot_id=self.id,
            sent_time=self.get_current_utc_datetime(),
            is_dm=is_dm
        )
        return final_response
