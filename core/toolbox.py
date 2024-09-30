from langchain.tools import tool
from asknews_sdk import AskNewsSDK
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
from newsapi import NewsApiClient
from datetime import datetime, timedelta
import ollama

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
    '''Use this tool if the user wants news on a particular topic.'''

    # get dates
    today = datetime.today().strftime('%Y-%m-%d')
    three_days_ago = (datetime.today() - timedelta(days=3)).strftime('%Y-%m-%d')

    num_articles = 3
    articles_meta = []

    # try with asknews
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

        for art_dict in articles.as_dicts:
            articles_meta.append({
                'title': art_dict.eng_title,
                'date': art_dict.pub_date,
                'url': art_dict.article_url,
                'summary': art_dict.summary
            })

    except Exception as e:
        pass

    # if not enough articles, try with newsapi
    if len(articles_meta) < num_articles:
        try:
            newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))

            articles = newsapi.get_everything(q=tool_input,
                                              sources='abc-news,abc-news-au,aftenposten,al-jazeera-english,ansa,associated-press,australian-financial-review,axios,bbc-news,bbc-sport,bloomberg,business-insider,cbc-news,cbs-news,cnn,financial-post,fortune',
                                              from_param=three_days_ago,
                                              to=today,
                                              language='en',
                                              sort_by='relevancy',
                                              page=1)

            articles_list = articles['articles'][:num_articles - len(articles_meta)]

            # create dictionary of articles
            for art_dict in articles_list:
                articles_meta.append({
                    'title': art_dict['title'],
                    'date': art_dict['publishedAt'],
                    'url': art_dict['url'],
                    'summary': art_dict['description']
                })

        except Exception as e:
            pass

    num_articles = len(articles_meta)
    if num_articles == 0:
        response = 'The tool did not work and I should tell the user.'
    else:
        response = f'Success! The tool has successfully retrieved {num_articles} articles on "{tool_input}".\n\n'
        sub_agent_prompt = 'Consider the following articles:\n\n'
        for i, art_dict in enumerate(articles_meta):
            title = art_dict['title']
            date = art_dict['date']
            url = art_dict['url']
            summary = art_dict['summary']
            sub_agent_prompt += f'Article {i + 1}: {title} ({date} UTC)\n{url}\n'
            sub_agent_prompt += f'Summary: {summary}\n\n'
        sub_agent_prompt += f'''
\n\nIgnore any results that are not about {tool_input}. Only consider articles in {agent.cfg.LANGUAGE}.
For each of these {num_articles} articles, respond to the user with a summary, why you think it might be interesting, and a hyperlink.
Each should be separated by a double line break '\n\n'.
'''
    sub_agent_response = call_llm(agent.model_name, response)
    print(sub_agent_response)

    return response + sub_agent_response

@tool
def parse_article(agent, tool_input: str) -> str:
    '''Use this tool get a well-structured and parsed version of the article from a url.'''
    # get the article from the url
    response = requests.get(tool_input)
    # check if the response is successful
    if response.status_code == 200:
        # parse the page using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        # get the raw text of the article
        text = soup.text
        response = f'Success! The tool has successfully parsed the article from the URL. Here is the article:\n\n{text}'
    else:
        response = f'The url was invalid. The tool did not work and I should tell the user.'

    return response

