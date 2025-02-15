from langchain.tools import tool
from dotenv import load_dotenv
from newsapi import NewsApiClient
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
def change_model(agent, tool_input: str) -> str:
    '''Use this tool to change the model to one of the available models.'''
    if tool_input in agent.cfg.AVAILABLE_MODELS:
        agent.model_name = tool_input
        response = f'Success! The tool has successfully changed the model to {agent.model_name}.'
        print(f"\nModel changed to {agent.model_name}\n")
    else:
        response = f'The model {tool_input} is not available. The available models are {agent.cfg.AVAILABLE_MODELS}.'
    return None, response

@tool
def search_news(agent, tool_input: str) -> str:
    '''Use this tool to search for news articles on a given topic.'''
    try:
        newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))

        articles = newsapi.get_everything(q=tool_input,
                                          sources='abc-news,abc-news-au,associated-press,australian-financial-review,axios,bbc-news,bbc-sport,bloomberg,business-insider,cbc-news,cbs-news,cnn,financial-post,fortune',
                                        #   from_param=self.last_month,
                                        #   to=self.today,
                                          language='en',
                                          sort_by='relevancy',
                                          page=1)
        
        top_article = articles['articles'][0]
        summary = top_article['description']
        url = top_article['url']

        response = f'''
        Success. Now, in the first line, respond in a fashion consistent with the agent's personality
        to the article summary. {summary}.
        On the second line, provide the URL to the full article: {url}
        '''

    except Exception as e:
        response = f'Error searching for news: {e}'

    return response


# @tool
# def tool_template(agent, tool_input: str) -> str:
#     '''
#     To add a tool, copy this template and modify it as needed. It just take `agent` and `tool_input` as arguments.
#     The agent will use the contents of this docstring to decide wheter to use this tool and which arguments to pass.
#     The response will be returned to the agent, who will have an opportunity to consider it then respond to the user.
#     The agent will response after the tool is used and is not allowed to consider additional tool before response.
#     '''
#     a = 3
#     b = 5
#     c = a + b
#     try:
#         response = f'''
#         Success! The tool worked. Now response to the user with the result. that {a} + {b} = {c}.
#         '''

#     except Exception as e:
#         response = f'Error searching for news: {e}'

    return response
