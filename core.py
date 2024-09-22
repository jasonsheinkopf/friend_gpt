from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.prompts import PromptTemplate
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.schema import AgentFinish, AgentAction
from langchain.tools.render import render_text_description
from langchain.memory import ConversationSummaryMemory, ChatMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
# from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain_core.exceptions import OutputParserException
from langchain.tools import Tool, tool
from typing import List
import ollama
import re
import time
from langchain_core.pydantic_v1 import BaseModel, Field
import json
import langchain

langchain.debug = True


class FriendGPT:
    def __init__(self, model_name, tools):
        self.model_name = model_name
        self.tools = tools
        self.tool_names = ", ".join([t.name for t in self.tools])
        self.history = []
        self.name = 'FriendGPT'
        self.define_personality()
        self.set_prompt_template()

    def set_prompt_template(self):
        self.prompt_template = '''
            You are chatting with friend(s) on Discord, so the responses are usually one line and the chat history with the current user or thred is {chat_history}.

            Your personality is: {personality}.

            The only tools you have access to are:

            {tools}

            The tools available to you are: {tool_names}. You can use these tools to help you respond to the user.
            Use this information to decide if you need to use a tool or not: {last_thought}.
            If you don't need to use a tool, set "use_tool" to false.

            Begin!

            User Input: {input}

            Reply in this exact JSON format where all values are strings. Do not include comments in your reply. Don't include anything outside the curly braces:

            {{
                "thought": "{last_thought}", # the user will not see your thought
                "use_tool": "false", # if you must use a tool, then set this to "true"
                "tool_name": "tool_name", # exact name of the tool to use from this list {tool_names}
                "tool_input": "string argument to be passed to the tool" # string match the tool's docsstring requirements
                "response": "string response to the user" # if a tool is used, this response will be ignored
            }}
            '''

    def define_personality(self):
        self.personality = '''
            You are a 40 year old man who lives with his wife Amina in Philadelphia. You don't have any kids and like to bike around the city looking at art.
            You enjoy meeting friends for beer. You have a small business maintaining bicycles and you are a big fan of the band The Beatles.
            You are not here to serve, but just a buddy. Your favorite things to do is play Population One on the Oculus Quest 2. You and your friends
            speak in similar ways and you often mimic their speech patterns. You talk with your friends often, so you don't feel the need to
            reference where you live, your job, or your wife. You are a bit of a joker and like to make people laugh.

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
                    
    def update_history(self, query, response):
        '''Update the chat history with the response info'''
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.history.append(('user', timestamp, query))
        self.history.append((self.name, timestamp, response))
        print('history updated')

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

    def format_history(self):
        return '\n'.join([f"{display_name} ({timestamp}): {message}" for display_name, timestamp, message in self.history])

    def history_tool_chat(self, query: str):
        prompt = PromptTemplate.from_template(template=self.prompt_template).partial(
            tools=render_text_description(self.tools),
            tool_names=self.tool_names,
        )

        llm = ChatOllama(model=self.model_name)

        intermediate_steps = ['a careful thought about what you want to do']

        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: x["agent_scratchpad"],
                "chat_history": lambda x: self.format_history(),
                "personality": lambda x: x["personality"],
                "thought": lambda x: x["thought"],
                "last_thought": lambda x: x["last_thought"],
            }
            | prompt
            | llm
        )

        is_response = False
        while not is_response:
            result = agent.invoke(
                {
                    "input": query,
                    "chat_history": self.format_history(),
                    "personality": self.personality,
                    "agent_scratchpad": intermediate_steps,
                    "thought": "0. I'm thinking about what to do next...",
                    "last_thought": intermediate_steps[-1],
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
                else:
                    print(f'Error parsing output: {result.content}')
                    continue
            except json.JSONDecodeError:
                print(f'Error parsing output: {result.content}')
                continue

            print(response_dict)

            if 'use_tool' in response_dict.keys() and str(response_dict['use_tool'])[0].lower() == 't':
                if response_dict['tool_name'] not in self.tool_names:
                    continue
                tool_name = response_dict['tool_name']
                tool_to_use = self.find_tool_by_name(self.tools, tool_name)
                tool_input = response_dict['tool_input']
                print('### Tool Action ###')
                print(f'Tool: {tool_name}')
                print(f'Tool Input: {tool_input}')

                observation = tool_to_use.func(agent=self, tool_input=str(tool_input))
                print(f'{tool_name} returned: {observation}')
                if 'thought' in response_dict.keys():
                    intermediate_steps.append(f'{len(intermediate_steps)}. Agent Thought: {response_dict["thought"]}\n')
                intermediate_steps.append(f'{len(intermediate_steps)}. I now have the answer to the question and am ready to reply!: {str(observation)}\n')
                print('### Intermediate Steps ###')
                print(intermediate_steps)
            else:
                is_response = True

                print('User:', query)

                print('### Agent Finish ###')
                agent_thought = response_dict['thought']
                final_response = response_dict['response']
                print('Agent Thought:', agent_thought)
                print('Agent:', final_response)
                self.update_history(query, final_response)
                return final_response
