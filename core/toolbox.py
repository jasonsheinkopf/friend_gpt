from langchain.tools import tool
from asknews_sdk import AskNewsSDK
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
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
    return None, response

@tool
def search_news(agent, tool_input: str) -> str:
    '''
    Use this tool only if the user asks specifically for news. Us it to search for a news article
    and summarize it to your short term memory.
    Do NOT use this tool if you are asked to discuss an article you have already read.
    tool_input: 1-2 word basic search terms for one relevant topic (excluding the word "news").
    '''
    search_term = tool_input

    # get recent chat history
    chat_history = agent.core_memory.get_formatted_chat_history(agent.current_channel, 2)

    # create instance of NewsSpecialist
    specialist = NewsSpecialist(agent.cfg)

    attempts = 0

    while attempts < 3:
        # get search term from chat history using LLM
        # search_term = specialist.get_search_term(chat_history)
        
        # select most relevant article using LLM
        top_article = specialist.get_top_article(search_term, chat_history)

        if top_article is None:
            break

        # retrieve the article text
        url, title, article_text = specialist.retrieve_article_text(top_article)

        # summarize the article
        article_summary = specialist.summarize_article(article_text)

        if article_summary is not None:
            # add the article to the agent's short term memory
            agent.short_term_memory = textwrap.dedent(f"""\
                You have read the following article:
                {title}

                From:
                {url}

                Article Summary:
                {article_summary}
                """)

            response = textwrap.dedent(f'''\
                The tool worked! Now do the following:
                    1) set "action": "respond"
                    2) share the url in your response: {url}
                    3) share this article summary: {article_summary}
                ''')
            return response
        else:
            response = f"No articles found on {search_term} Respond to the user to let them know. Don't try again."

            print(f'No articles found on ({search_term}). Attempt {attempts + 1}')
            attempts += 1

    return response
