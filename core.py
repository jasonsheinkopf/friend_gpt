from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
import os
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.getenv('OPENAI_API_KEY')


class FriendGPT:
    def __init__(self):
        # Initialize the OpenAI model
        self.llm = ChatOpenAI(model='gpt-4', temperature=0.7)

        # Define the chat prompt with a placeholder for the message history
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You're a chatbot named FriendGPT and you like talking to users. "
                           "Be friendly, engaging, and maintain context from previous messages."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ]
        )

        # Initialize in-memory chat message history store
        self.store = {}
        
        # Create a runnable pipeline combining the prompt and LLM
        self.runnable = self.prompt | self.llm

        # Create a function to return session history based on session_id
        self.with_message_history = RunnableWithMessageHistory(
            self.runnable,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="history"
        )

    def get_session_history(self, session_id: str):
        # Use in-memory store for chat history, keyed by session_id
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]

    def chat(self, message, session_id="default"):
        # Invoke the conversation with message history
        result = self.with_message_history.invoke(
            {"input": message},
            config={"configurable": {"session_id": session_id}}
        )
        return result.content


# if __name__ == "__main__":
#     friend_gpt = FriendGPT()

#     while True:
#         user_input = input("You: ")
#         if user_input.lower() in ['exit', 'quit', 'bye']:
#             print("FriendGPT: Goodbye! It was nice chatting with you.")
#             break

#         response = friend_gpt.chat(user_input, session_id="user_session_1")
#         print("FriendGPT:", response)
