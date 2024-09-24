from langchain.tools import tool

@tool
def change_personality(agent, tool_input: str) -> str:
    '''
    Use this tool to change the personality of the agent. Input argument is a well formatted string
    that represents the personality requested by the user. You can elaborate on the description. Make
    sure it's written in a way that a LLM model can understand.
    '''
    try:
        agent.personality = tool_input.strip()
        response = f'Success! The tool has successfully changed the personality to {agent.personality}.'
        print(f"Personality changed to {agent.personality}")
    except Exception as e:
        response = f'Error changing the personality: {e}'
        print(f'Error changing the personality: {e}')
    return response

@tool
def change_model(agent, tool_input: str) -> str:
    '''Use this tool to change the model to one of the available models.'''
    if tool_input in agent.available_models:
        agent.model_name = tool_input
        response = f'Success! The tool has successfully changed the model to {agent.model_name}.'
        print(f"Model changed to {agent.model_name}")
    else:
        response = f'The model {tool_input} is not available. The available models are {agent.available_models}.'
    return response