from fvcore.common.config import CfgNode

_C = CfgNode()

_C.CORE_MEMORY_PATH = "memories/core_memory.db"

_C.MODEL = "gpt-4o-mini"

_C.NEWS_MODEL = "llama3.1:8b"

_C.SUMMARY_MODEL = "llama3.1:8b"

_C.SUMMARIZE_CHAT_HISTORY_EMBEDDINGS = True

_C.SUMMARIZE_CHAT_PROMPT = '''
Summarize the following chat history
The first line should be only the last date show [YYYY-MM-DD],
Then, include individual lines of factual statements about what occurred.
Using names and never pronouns.
Include no blank lines.
There should be absolutely nothing before the date.

Example:
2022-01-01
Steve said his favorite color is orange.
Mary said she also likes orange.
Steve and Mary both agreed to go to the park together the next day.

Chat History:
{formatted_chunk_string}
'''

_C.AVAILABLE_MODELS = [
    'llama3.1:8b',
    'gemma2:9b',
    'phi3:latest',
    'gpt-4o-mini'
]

# remove {discord_bot_username} if you want to create a custom name
# _C.STARTER_PERSONALITY = '''You're playing the role a real person named {agent_username}
# chatting with your friends on Discord. You are very smart and very knowledgeable and likeable.
# You don't speak in large chunks of text, but shorter messages
# like people normally do on Discord. Sometimes, you make spelling mistakes like people normally do.
# You have a good memory of what people have said to you and you can remember facts about them.
# You have your own life and can make up those details as you go. You're not a robot, but a person.
# Even though you're playing the role of a real person, you have all the knowledge of the internet.
# '''

_C.STARTER_PERSONALITY = '''You're a smart, knowledgeable, and helpful Discord bot named {agent_username}.
You don't speak in large chunks of text, but shorter messages like people normally do on Discord.
You like to help people and are very friendly. You have a good memory of what people have said to you.
You follow instructions extremely well.
'''

# True to always use starter personality, False to use dynamic personality from database
_C.USE_STARTER_PERSONALITY = True

_C.PERSONALITY_PATH = 'memories/personality.txt'

# typing speed in characters per second
_C.TYPING_SPEED = 50

# length of chat history tail to show in the prompt
_C.LONG_HISTORY_LENGTH = 15

# length of chat history tail to generate response to
_C.SHORT_HISTORY_LENGTH = 2

# the length of history tail to use for vector search
_C.VECTOR_SEARCH_LENGTH = 1

# path to save long term vector memory
_C.CHAT_VECTOR_MEMORY_PATH = 'memories/chat_vector_memory.faiss'

# chat threshold after which recent chat history should by ingested to vector memory
_C.CHAT_VECTOR_MEMORY_MIN_CHUNK_SIZE = 10

# duration in seconds between checking for vector chat history to ingest
_C.CHAT_VECTOR_MEMORY_INTERVAL = 10

# embedding model name for SentenceTransformers
_C.CHAT_VECTOR_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

_C.CHAT_EMBED_NEIGHBORS = 32

# number of vector chat search results to include in prompt
_C.NUM_LONG_TERM_MEMORY_RETRIEVALS = 4

_C.LANGUAGE = 'english'


def get_cfg():
    """
    Get a copy of the config node.
    """
    return _C.clone()
