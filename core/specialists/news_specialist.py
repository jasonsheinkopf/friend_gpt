from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from datetime import datetime, timedelta
from asknews_sdk import AskNewsSDK
import os
from newsapi import NewsApiClient
import requests
import re
from bs4 import BeautifulSoup
import textwrap


class NewsSpecialist:
    def __init__(self, cfg):
        self.cfg = cfg
        self.today = datetime.today().strftime('%Y-%m-%d')
        self.last_month = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.num_articles = 10
        self.articles_meta = []
        self.api_error = ''

    def get_search_term(self, context):
        '''Returns most likely search term based on the context'''
        search_term_prompt_template = textwrap.dedent(f'''\
            Consider the chat context below. You need to think carefully about
            one single news topic to create a correctly-spelled and formatted search term for.
            Focus on the last topic discussed and don't mix up multiple topics. What are the most important. Generate a
            few keywords to use in a news API search. Consider the last line the most significant.

            Context:
            {context}

            Only reply with one keyord search. Nothing before or after it. Exclude the word "news"
            Keywords:
            ''')
        prompt = PromptTemplate.from_template(search_term_prompt_template)
        llm = ChatOllama(model=self.cfg.NEWS_MODEL)

        agent = (
            {
                'context': lambda x: x['context'],
            }
            | prompt
            | llm
        )

        result = agent.invoke({
            'context': context,
        })
        print(f'Response from get_search_term: {result.content}')
        return result.content.replace('news', '')

    def get_articles_meta(self, topic):
        '''
        Get the metadata of the articles from news APIs
        '''
        # try:
        #     sdk = AskNewsSDK(
        #         client_id=os.getenv('ASKNEWS_CLIENT_ID'),
        #         client_secret=os.getenv('ASKNEWS_CLIENT_SECRET'),
        #         scopes=['news']
        #     )
        #     articles = sdk.news.search_news(
        #         query=topic,
        #         n_articles=self.num_articles,
        #         return_type='dicts',
        #         method='nl',
        #     )

        #     for art_dict in articles.as_dicts:
        #         self.articles_meta.append({
        #             'title': art_dict.eng_title,
        #             'date': art_dict.pub_date,
        #             'url': art_dict.article_url,
        #             'summary': art_dict.summary
        #         })

        # except Exception as e:
        #     self.api_error += f'AskNews API error: {e}\n'
        #     # print(f'AskNews API error: {e}')

        # if not enough articles, try with newsapi
        # if len(self.articles_meta) < self.num_articles:
        try:
            newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))

            articles = newsapi.get_everything(q=topic,
                                              sources='abc-news,abc-news-au,associated-press,australian-financial-review,axios,bbc-news,bbc-sport,bloomberg,business-insider,cbc-news,cbs-news,cnn,financial-post,fortune',
                                              from_param=self.last_month,
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

    def get_top_article(self, topic, chat_history):
        self.get_articles_meta(topic)
        # print(self.articles_meta)
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
            specialist_prompt_template = textwrap.dedent(f'''\
                You are a news specialist. You have been asked to select one article in the language {self.cfg.LANGUAGE}
                from this list that is most relevant to the context of this conversation.

                Chat Context:
                {chat_history}

                Articles:
                {formatted_articles_meta}

                Don't preface your reply or include anything other than a one sentence summary of the article and the url.
                ''')

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
            print(f'Response from get_top_article: {result.content}')
            return result.content

        else:
            return None

    def retrieve_article_text(self, article):
        # Regex pattern for extracting URLs
        url_pattern = r'(https?://[^\s]+)'

        # Regex for title: Extract everything before the URL
        match = re.search(url_pattern, article)
        if match:
            title = article[:match.start()].strip()  # Get everything before the URL
        else:
            title = "No title found"

        # Find all URLs in the text
        url = re.findall(url_pattern, article)
        if len(url) == 0:
            return None, None, None
        else:
            url = url[0]

        # Add headers to simulate a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36'
        }

        # use beautiful soup to extract the article content
        response = requests.get(url, headers=headers)
        
        # check if the request was successful
        if response.status_code == 200:
            # parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')

            # find the article content
            article_text = soup.get_text(strip=True)
        else:
            article_text = None

        return url, title, article_text
    
    def summarize_article(self, article_text):
        ''' Summarizes the article text using LLM '''
        article_summary_prompt_template = textwrap.dedent(f'''\
            Summarize the following article in three paragraphs.
            Make sure to note key details and the main points of the article. It's very important that you
            do not make anything up. You must only summarize the information that is in the article.

            Article Content:
            {article_text}

            Three Paragraph Summary:
            ''')
        prompt = PromptTemplate.from_template(article_summary_prompt_template)
        llm = ChatOllama(model=self.cfg.NEWS_MODEL)

        agent = (
            {
                'article_text': lambda x: x['article_text'],
            }
            | prompt
            | llm
        )

        result = agent.invoke({
            'article_text': article_text,
        })
        print(f'\nResponse from summarize_article:\n{result.content}')
        return result.content

