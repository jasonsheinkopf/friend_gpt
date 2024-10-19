from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from datetime import datetime, timedelta
import os
from newsapi import NewsApiClient
import requests
import re
from bs4 import BeautifulSoup
import textwrap


class NewsSpecialist:
    def __init__(self, cfg, chat_history):
        self.cfg = cfg
        self.today = datetime.today().strftime('%Y-%m-%d')
        self.last_month = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.num_articles = 10
        self.articles_meta = []
        self.api_error = ''
        self.chat_history = chat_history

    def get_search_term(self):
        '''Returns most likely search term based on the chat history'''
        search_term_prompt_template = textwrap.dedent(f'''\
            Consider the chat history. You need to think carefully about
            one single news topic to create a correctly-spelled and formatted search query for.
            Focus on the last topic discussed and don't mix up multiple topics. Generate a
            few keywords to use in a news API search. Consider the last chat line to be most significant.

            Chat History:
            {self.chat_history}

            Only reply with keyword search. Nothing before or after it. Exclude the word "news"
            Keywords:
            ''')

        llm = ChatOllama(model=self.cfg.NEWS_MODEL)

        result = llm.invoke(search_term_prompt_template)
        print(f'Response from get_search_term: {result.content}')
        return result.content.replace('news', '')

    def get_articles_meta(self, search_term):
        '''
        Get the metadata of the articles from news APIs
        '''
        try:
            newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))

            articles = newsapi.get_everything(q=search_term,
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

    def get_top_article(self, search_term):
        self.get_articles_meta(search_term)
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
                You are a news specialist. The following chat history includes a request for news.
                {self.chat_history}

                You need to decide if any of theese articles are relevant to the chat history. Only
                consider articles in the {self.cfg.LANGUAGE} language.

                If none of the articles are relevant, reply with "None of the articles are relevant."
                Otherwise, reply with the title of the most relevant article and the url.

                Articles:
                {formatted_articles_meta}

                Don't preface your reply or include anything other than summary of the article and the url.
                **If none of the articles are relevant, reply with "None of the articles are relevant.**"
                ''')

            llm = ChatOllama(model=self.cfg.NEWS_MODEL)

            print(f'Specialist prompt: {specialist_prompt_template}')

            result = llm.invoke(specialist_prompt_template)
            print(f'Response from get_top_article: {result.content}')
            return result.content

        else:
            return None

    def retrieve_article_text(self, article):
        # Regex pattern for extracting URLs
        url_pattern = r'(https?://[^\s]+)'

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

        return url, article_text
    
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
        llm = ChatOllama(model=self.cfg.NEWS_MODEL)

        result = llm.invoke(article_summary_prompt_template)
        print(f'Response from summarize_article: {result.content}')
        return result.content

    def get_news_summary_workflow(self, chat_history):
        ''' Get the URL and summary of the top article '''
        attempts = 0
        article_summary = None
        url = None

        while attempts < 3 and not article_summary:
            # get search term
            search_term = self.get_search_term()
            print(f'Search term: {search_term}')

            # search for articlee metadata and select most relevant
            top_article = self.get_top_article(search_term)
            print(f'Top article: {top_article}')

            if top_article is None:
                break

            # retrieve the article text by scraping the url
            url, article_text = self.retrieve_article_text(top_article)
            print(f'URL: {url}')
            print(f'Article text: {article_text}')

            # summarize the article
            article_summary = self.summarize_article(article_text)
            print(f'Article summary: {article_summary}')

            if article_summary is not None:
                break
            
            attempts += 1

        return url, article_summary
