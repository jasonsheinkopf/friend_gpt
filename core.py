from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


class FriendGPT:
    def __init__(self, model_name):
        self.model_name = model_name
        self.template = """
        You are a chat agent named Friend GPT. You are buddies with the users and act just like one of the boys.
        You're not here to serve them, but to be their friend.
        """

    def get_token_count(self, result):

    def send_prompt(self, message):
        prompt_template = ChatPromptTemplate(self.template)
        llm = ChatOllama(model=self.model_name)
        agent = prompt_template | llm
        result = agent.invoke(
            {
                'input': message,
            }
        )
        return result.content