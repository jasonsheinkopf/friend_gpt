# <img src="media/friend.jpeg" alt="Your GIF" width="25"> Friend GPT 
Friend GPT is an customizable LLM agent with memory that can interact through Discord private chats and servers. It can be
served by API to closed-source models or locally through Ollama.

# Novel Response Method
To simulate a more human interaction, the agent does not respond once per prompt. Instead new messages are added to the
chat history by an independent thread and can be done while the agent is processing response. The model thread checks the recent
chat history every second and is prompted to respond to the context of the last few messages.

# Short Term Memory
Chat messages are stored in a SQLite db chat_history table. User can customize the length of the tail to be included in the prompt to the agent.
<img src="media/chat_history.jpeg" alt="Your GIF" width="800">

# Long Term Vector Memory
The model regularly checks if the length of short term memory is past a threshold. If so, the undigested history is summarized with
an additional LLM call, embedded into vector space by SentenceTransformers, and added to a FAISS vector index. Each text chunk is then added to a
different chat_vector_memory table in the db along with its retrivel index. Each agent prompt includes results from the top 3 most relevant
chunks retrieved by vector similarity.

# Personality
The agent's personality can be easily set in the cfg file. However, it is able to change its own personality using a tool. This
personality can persist between session by enabling the option in the cfg file.

# Tools
The agent is instructed to think through its response and consider using the available tools. Additional tools can easily
be added by writing new functions in the toolbox file and using the @tool decorator.
<img src="media/no_tool.jpeg" alt="Your GIF" width="800">
<img src="media/use_tool" alt="Your GIF" width="800">
