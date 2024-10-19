from langchain.tools import tool
from dotenv import load_dotenv
from core.specialists.news_specialist import NewsSpecialist
import textwrap
from langdetect import detect

load_dotenv()

@tool
def change_personality(agent, tool_input: str) -> str:
    '''
    Use this tool to completely change the personality of the agent when requested. The tool_input
    must always be self-contained and not rely on any external information.
    '''
    try:
        agent.personality = tool_input.strip()
        response = f"Success! The tool has successfully changed the {agent.name}'s personality to {agent.personality}."
        with open(agent.cfg.PERSONALITY_PATH, 'w') as f:
            f.write(agent.personality)
        print(f"\nPersonality changed to {agent.personality}\n")
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
        print(f"\nModel changed to {agent.model_name}\n")
    else:
        response = f'The model {tool_input} is not available. The available models are {agent.available_models}.'
    return None, response

@tool
def search_news(agent, tool_input: str) -> str:
    '''
    Use this tool only if the user asks specifically for news. Use it to so search for news articles,
    summarize them, and provide the user with the URL and summary of the most relevant article.
    Do NOT use this tool if you are asked to discuss an article you have already read.
    tool_input: the last 4 complete lines of chat history ignoring timestamps
    '''
    chat_history = tool_input

    # create instance of NewsSpecialist
    specialist = NewsSpecialist(agent.cfg, chat_history)

    url, article_summary = specialist.get_news_summary_workflow(chat_history)

    if article_summary is not None:
        response = textwrap.dedent(f'''\
            The tool worked! Now share the url:
            {url}
            
            And share the article summary:
            {article_summary}
            ''')
        return response
    else:
        response = f"No articles found. Respond to the user to let them know. Don't try again."

        print(f'No articles found.')

    return response
