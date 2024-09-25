from langchain.tools import tool
from asknews_sdk import AskNewsSDK
from dotenv import load_dotenv
import os

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
def embellish_personality(agent, tool_input: str) -> str:
    '''
    Use this tool to add another line of detail to your personality. You can do this to incorporate
    new information about yourself that you have learned from your thoughts or conversations. 
    '''
    try:
        # add one line to the end of personality file
        with open(agent.cfg.PERSONALITY_PATH, 'a') as f:
            f.write(f"\n{tool_input.strip()}")
        response = f"Success! The tool has successfully added {agent.personality} to {agent.name}'s personality."
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
    return response

@tool
def search_news(agent, tool_input: str) -> str:
    '''Use this tool to search for news articles on a given topic and provide a summary and hyperlink.'''
    num_articles = 3
    try:
        sdk = AskNewsSDK(
            client_id=os.getenv('ASKNEWS_CLIENT_ID'),
            client_secret=os.getenv('ASKNEWS_CLIENT_SECRET'),
            scopes=['news']
        )
        articles = sdk.news.search_news(
            query=tool_input,
            n_articles=num_articles,
            return_type='dicts',
            method='nl',
        )
        response = f'''Success! The tool has successfully retreived 3 articles on "{tool_input}".'''
        for i, art_dict in enumerate(articles.as_dicts):
            title = art_dict.eng_title
            date = art_dict.pub_date
            url = art_dict.article_url
            summary = art_dict.summary
            response += f'Article {i + 1}: {title} ({date} UTC)\n{url}\n'
            response += f'Summary: {summary}\n\n'
        response += f'\n\nNow, summarize these articles and provide a hyper link to the best one in {agent.cfg.LANGUAGE}.'
    except Exception as e:
        response = f'There was an error with this API call: {e}. The tool did not work and I should tell the user.'
    return response
