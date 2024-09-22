from langchain.tools import Tool, tool

@tool
def summarize_chat(agent, tool_input: str) -> str:
    '''Use this tool if the provide a summary of a given chat history. Input argument is empty string.'''
    recent_history = agent.history
    return '\n'.join([f"{display_name}: {message}" for display_name, timestamp, message in recent_history])

@tool
def get_magic_number(agent, tool_input: str) -> str:
    '''Use this tool to discover the magic number'''
    response = '''
    The tool has already been used. Do NOT use it again.
    Make sure to set "use_tool" to "false" in the JSON input.
    The magic number is 57.
    Don't use the tool.
    Set use tool to false!
    '''
    return response