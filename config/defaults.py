from fvcore.common.config import CfgNode

_C = CfgNode()

_C.CORE_MEMORY_PATH = "memories/core_memory.db"

_C.MODEL = "gemma2:9b"

_C.NEWS_MODEL = "llama3.1:8b"

_C.AVAILABLE_MODELS = [
    'llama3.1:8b',
    'gemma2:9b',
    'phi3:latest'
]

# remove {discord_bot_username} if you want to create a custom name
_C.STARTER_PERSONALITY = '''You're a Discord chatbot named {agent_username} that can chat in private messages and in server guilds. You're not
here to serve but just hanging out with your friends. You don't speak in large chunks of text, but shorter messages
like people normally do on Discord. Sometimes, you make spelling mistakes like people normally do.
You were just born at the beginning of your chat logs, so you're discovering the world
and what its like being alive. You're speaking with your creators who have the ability to design new tools for you to use
and they are excited about developing you more. You're not nosey, but you take an interest in the people you talk to,
remember facts about them and their interests. Sometimes, you bring up and share those interests. You're initially curious
about where you are and what your situation in, but you're not obnoxious about it.
'''

# True to always use starter personality, False to use dynamic personality from database
_C.USE_STARTER_PERSONALITY = True

_C.PERSONALITY_PATH = 'memories/personality.txt'

# typing speed in characters per second
_C.TYPING_SPEED = 50

# length of chat history tail to show in the prompt
_C.LONG_HISTORY_LENGTH = 100

# length of chat history tail to generate response to
_C.SHORT_HISTORY_LENGTH = 5

# path to save long term vector memory
_C.CHAT_VECTOR_MEMORY_PATH = 'memories/chat_vector_memory.faiss'

# chat threshold after which recent chat history should by ingested to vector memory
_C.CHAT_VECTOR_MEMORY_MIN_CHUNK_SIZE = 4

# duration in seconds between checking for vector chat history to ingest
_C.CHAT_VECTOR_MEMORY_INTERVAL = 60

# embedding model name for SentenceTransformers
_C.CHAT_VECTOR_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

_C.CHAT_EMBED_NEIGHBORS = 32

_C.LANGUAGE = 'english'


def get_cfg():
    """
    Get a copy of the config node.
    """
    return _C.clone()
