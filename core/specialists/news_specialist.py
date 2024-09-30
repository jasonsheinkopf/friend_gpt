from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from datetime import datetime, timedelta
from asknews_sdk import AskNewsSDK
import os
from newsapi import NewsApiClient

from dotenv import load_dotenv

class NewsSpecialist:
    def __init__(self, cfg):
        self.cfg = cfg
        self.today = datetime.today().strftime('%Y-%m-%d')
        self.last_week = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')
        self.num_articles = 10
        self.articles_meta = []
        self.api_error = ''

    def get_articles_meta(self, topic):
        '''
        Get the metadata of the articles from news APIs
        '''
        try:
            sdk = AskNewsSDK(
                client_id=os.getenv('ASKNEWS_CLIENT_ID'),
                client_secret=os.getenv('ASKNEWS_CLIENT_SECRET'),
                scopes=['news']
            )
            articles = sdk.news.search_news(
                query=topic,
                n_articles=self.num_articles,
                return_type='dicts',
                method='nl',
            )

            for art_dict in articles.as_dicts:
                self.articles_meta.append({
                    'title': art_dict.eng_title,
                    'date': art_dict.pub_date,
                    'url': art_dict.article_url,
                    'summary': art_dict.summary
                })

        except Exception as e:
            self.api_error += f'AskNews API error: {e}\n'
            # print(f'AskNews API error: {e}')

        # if not enough articles, try with newsapi
        if len(self.articles_meta) < self.num_articles:
            try:
                newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))

                articles = newsapi.get_everything(q=topic,
                                                #   sources='abc-news,abc-news-au,aftenposten,al-jazeera-english,ansa,associated-press,australian-financial-review,axios,bbc-news,bbc-sport,bloomberg,business-insider,cbc-news,cbs-news,cnn,financial-post,fortune',
                                                  from_param=self.last_week,
                                                  to=self.today,
                                                  language='en',
                                                  sort_by='relevancy',
                                                  page=1)

                # don't exceed the max number of articles
                articles_list = articles['articles'][:self.num_articles - len(self.articles_meta)]

                # create dictionary of articles
                for art_dict in articles_list:
                    self.articles_meta.append({
                        'title': art_dict['title'],
                        'date': art_dict['publishedAt'],
                        'url': art_dict['url'],
                        'summary': art_dict['description']
                    })

            except Exception as e:
                self.api_error += f'NewsAPI error: {e}\n'
                # print(f'NewsAPI error: {e}')

    def get_top_article(self, topic):
        self.get_articles_meta(topic)
        num_articles = len(self.articles_meta)
        if num_articles > 0:
            formatted_articles_meta = ''
            for art_dict in self.articles_meta:
                title = art_dict['title']
                date = art_dict['date']
                url = art_dict['url']
                summary = art_dict['summary']
                formatted_articles_meta += f'{title} ({date} UTC)\n{url}\n'
                formatted_articles_meta += f'Summary: {summary}\n\n'
            specialist_prompt_template = f'''
You are a news specialist. You have been asked to select one article from this list that is most relevant to
the user's query: {topic}. Only consider articles in {self.cfg.LANGUAGE}.

Articles:
{formatted_articles_meta}

Reply with a one sentence summary of the article you have selected followed by the url on the next line.
'''     

            prompt = PromptTemplate.from_template(specialist_prompt_template)
            llm = ChatOllama(model=self.cfg.NEWS_MODEL)

            agent = (
                {
                    'topic': lambda x: x['topic'],
                    'language': lambda x: x['language'],
                    'articles_meta': lambda x: x['articles_meta'],
                }
                | prompt
                | llm
            )

            result = agent.invoke({
                'topic': topic,
                'language': self.cfg.LANGUAGE,
                'articles_meta': self.articles_meta,
            })

            return result.content

        else:
            return f'No articles were found for the topic {topic}.'
        