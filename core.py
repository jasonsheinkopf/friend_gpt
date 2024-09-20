import openai
from dotenv import load_dotenv
import os

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


class FriendGPT():
    def chat(self, message):
        response = openai.Completion.create(
            engine="davinci",
            prompt=message,
            max_tokens=100
        )
        return response.choices[0].text.strip()

