from langchain.tools import tool

@tool
def change_personality(agent, tool_input: str) -> str:
    '''
    Use this tool to change the personality of the agent. Input argument is a well formatted string
    that represents the personality requested by the user. You can elaborate on the description. Make
    sure it's written in a way that a LLM model can understand.
    '''
    agent.personality = tool_input
    response = f'''
    The personality has successfully been changed.
    Now respond to the user and don't use the tool again.
    Don't use the tool! Don't use the tool!
    '''
    print(f"Personality changed to {agent.personality}")
    return response

@tool
def change_model(agent, tool_input: str) -> str:
    '''Use this tool to change the model to one of the available models'''
    if tool_input in agent.available_models:
        agent.model_name = tool_input
        response = f'''
        The model cas successfully been changed to {agent.model_name}.
        Now respond to the user and don't use the tool again.
        Don't use the tool! Don't use the tool!
        '''
        print(f"Model changed to {agent.model_name}")
    else:
        response = f'The model {tool_input} is not available. The available models are {agent.available_models}.'
    return response