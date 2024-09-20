from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI()


class FriendGPT():
    def chat(self, message):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message},
            ]
        )
        return response.choices[0].message.content


# print(FriendGPT().chat('Hello, how are you?'))