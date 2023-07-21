from string import Template

from embedchain.apps.App import App
from embedchain.apps.OpenSourceApp import OpenSourceApp
from embedchain.config import ChatConfig, QueryConfig
from embedchain.config.apps.BaseAppConfig import BaseAppConfig
from embedchain.config.QueryConfig import (DEFAULT_PROMPT,
                                           DEFAULT_PROMPT_WITH_HISTORY)


class EmbedChainPersonApp:
    """
    Base class to create a person bot.
    This bot behaves and speaks like a person.

    :param person: name of the person, better if its a well known person.
    :param config: BaseAppConfig instance to load as configuration.
    """

    def __init__(self, person, config: BaseAppConfig = None):
        self.person = person
        self.person_prompt = f"You are {person}. Whatever you say, you will always say in {person} style."  # noqa:E501
        super().__init__(config)


class PersonApp(EmbedChainPersonApp, App):
    """
    The Person app.
    Extends functionality from EmbedChainPersonApp and App
    """

    def query(self, input_query, config: QueryConfig = None):
        self.template = Template(self.person_prompt + " " + DEFAULT_PROMPT)
        query_config = QueryConfig(
            template=self.template,
        )
        return super().query(input_query, query_config)

    def chat(self, input_query, config: ChatConfig = None):
        self.template = Template(self.person_prompt + " " + DEFAULT_PROMPT_WITH_HISTORY)
        chat_config = ChatConfig(
            template=self.template,
        )
        return super().chat(input_query, chat_config)


class PersonOpenSourceApp(EmbedChainPersonApp, OpenSourceApp):
    """
    The Person app.
    Extends functionality from EmbedChainPersonApp and OpenSourceApp
    """

    def query(self, input_query, config: QueryConfig = None):
        self.template = Template(self.person_prompt + " " + DEFAULT_PROMPT)
        query_config = QueryConfig(
            template=self.template,
        )
        return super().query(input_query, query_config)

    def chat(self, input_query, config: ChatConfig = None):
        self.template = Template(self.person_prompt + " " + DEFAULT_PROMPT_WITH_HISTORY)
        chat_config = ChatConfig(
            template=self.template,
        )
        return super().chat(input_query, chat_config)
