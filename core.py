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


class FriendGPT:
    def __init__(self, model_name):
        self.model_name = model_name
        self.tools = []
        self.history = []
        self.name = 'FriendGPT'
        self.define_personality()
        self.set_prompt_template()

    def set_prompt_template(self):
        self.prompt_template = '''
            You are chatting with friend(s) on Discord, so the responses are usually one line and the chat history with the current user or thred is {chat_history}.
            Your personality is: {personality}. You always stay in character and never break the fourth wall.

            Your response is to either use an Action or provide a Final Answer but not both.
            The following tools are available to you:

            {tools}
            
            ---- Action Format ----
            If you want to perform an Action, you must include the following:
            Thought: think carefully about what you want to do
            Action: you must include the action you want to take, should be one of [{tool_names}]
            Action Input: you must include the input to the tool.

            ---- Example Action Response ----
            Thought: I need to use a tool called example_action
            Action: example_action
            Action Input: example string argument for action function call

            ---- Final Answer Format ----
            To provide a Final Answer, reply in this exact format with no exceptions:
            Thought: you must say what you are thinking just before you provide your final answer
            Final Answer: your final answer. If not using a tool, you must provide a final answer

            ---- Example Final Answer Response ----
            Thought: The human wants me to tell them how to get to the store
            Final Answer: Turn left at the stop sign and the store will be on your right

            Begin!

            User Input: {input}
            Thought: {agent_scratchpad}
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
                    
    def update_history(self, query, result):
        '''Update the chat history with the response info'''
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.history.append(('user', timestamp, query))
        self.history.append((self.name, timestamp, result.content))

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
        for line in self.history:
            print(line)
        return '\n'.join([f"{display_name} ({timestamp}): {message}" for display_name, timestamp, message in self.history])

    def history_tool_chat(self, query: str):
        prompt = PromptTemplate.from_template(template=self.prompt_template).partial(
            tools=render_text_description(self.tools),
            tool_names=", ".join([t.name for t in self.tools]),
        )

        llm = ChatOllama(model=self.model_name)

        intermediate_steps = []

        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_log_to_str(x["agent_scratchpad"]),
                "chat_history": lambda x: self.format_history(),
                "personality": lambda x: x["personality"],
            }
            | prompt
            | llm
        )

        agent_step = ''
        while not isinstance(agent_step, AgentFinish):
            result = agent.invoke(
                {
                    "input": query,
                    "chat_history": self.format_history(),
                    "personality": self.personality,
                    "agent_scratchpad": intermediate_steps,
                }
            )

            try:
                agent_step = ReActSingleInputOutputParser().parse(result.content)
            except OutputParserException:
                print(f'### Parsing Error ###')
                break

            if isinstance(agent_step, AgentAction):
                tool_name = agent_step.tool
                tool_to_use = self.find_tool_by_name(self.tools, tool_name)
                tool_input = agent_step.tool_input
                print('### Tool Action ###')
                print(f'Tool: {tool_name}')
                print(f'Tool Input: {tool_input}')

                observation = tool_to_use.func(str(tool_input))
                print(f'Observation: {observation}')
                intermediate_steps.append((agent_step, str(observation)))

        print('User:', query)

        if isinstance(agent_step, AgentFinish):
            print('### Agent Finish ###')
            agent_thought = agent_step.log
            match = re.search(r'(?<=Thought:)(.*?)(?=Final Answer:)', agent_thought, re.DOTALL)
            if match:
                thought = match.group(1).strip()
                print(thought)
            else:
                thought = ''
            final_response = agent_step.return_values['output']
            # print('Agent:', final_response)
            self.update_history(query, final_response)
            return final_response
        else:
            # print('Agent:', result.content)
            self.update_history(query, result)
        return result.content

    # def send_prompt(self, message):
    #     prompt_template = ChatPromptTemplate(self.template)
    #     llm = ChatOllama(model=self.model_name)

    #     # Format the prompt with the user's message
    #     formatted_prompt = prompt_template.format(input=message)

    #     # Print the exact prompt being sent to the LLM
    #     print("Prompt being sent to the LLM:")
    #     print(formatted_prompt)

    #     agent = prompt_template | llm
    #     result = agent.invoke(
    #         {
    #             'input': message,
    #         }
    #     )
    #     self.get_token_count(result)
    #     return result.content