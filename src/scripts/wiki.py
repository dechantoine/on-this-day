import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import re
from typing import Self
from urllib.parse import unquote
import os

from loguru import logger
import numpy as np
from tqdm import tqdm
import wikipedia

from src.config import settings
from src.gemini import LLMGemini
from src.scripts.prompts import extract_events, choose_page, short_summary, qualify_event
from src.schemas import Event, Events, Page, IdentifiedCriteria, QualifiedEvent

wikipedia.set_lang("en")

html_events_header = '<div class="mw-heading mw-heading2"><h2 id="Events">Events</h2>'
html_births_header = '<div class="mw-heading mw-heading2"><h2 id="Births">Births</h2>'
html_page_table_end = '</table>\n<p>'
html_page_references_begin = '<div class="mw-heading mw-heading2"><h2 id="References">References</h2>'

re_href = re.compile(r'<a href="/wiki/[^":]+"')


class WikiPage(Page):
    def __init__(self, page_title: str = None) -> None:
        """Initialize a WikiPage object with the title of the page

        Args:
            page_title (str): the title of the page
        """
        page_content = ""
        page_html = ""
        hrefs = []
        super().__init__(page_title=page_title,
                         page_content=page_content,
                         page_html=page_html,
                         hrefs=hrefs)

        if page_title:
            self.page_title = unquote(
                self.page_title
                .replace('/wiki/', "")
                .replace('_', " ")
            )
            try:
                self.page_content, self.page_html = self.load_page(self.page_title)
            except Exception as e:
                logger.warning(e)
                self.page_content = ""
                self.page_html = ""
            self.hrefs = self.load_hrefs()

    def __str__(self):
        return self.page_content

    def to_dict(self) -> dict:
        return {
            'page_title': self.page_title,
            'page_content': self.page_content,
            'page_html': self.page_html,
            'hrefs': self.hrefs
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        instance = cls()
        instance.page_title = data['page_title']
        instance.page_content = data['page_content']
        instance.page_html = data['page_html']
        instance.hrefs = data['hrefs']
        return instance

    def save_to_json(self, file_path: str) -> None:
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(file_path, 'w') as file:
            json.dump(self.to_dict(), file)

    @classmethod
    def load_from_json(cls, file_path: str) -> Self:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return cls.from_dict(data)

    def load_page(self, page_title: str) -> tuple[str, str]:
        """Download a Wikipedia page with the title

        Args:
            page_title (str): the title of the page

        Returns:
            tuple[str, str]: the content and the HTML of the page
        """
        try:
            page = wikipedia.page(title=page_title,
                                  auto_suggest=False,
                                  preload=False)
        except wikipedia.exceptions.PageError:
            suggestions = wikipedia.search(query=page_title,
                                           results=5)
            raise ValueError(f"Page '{page_title}' not found. Suggestions: {suggestions}")
        except KeyError as e:
            raise e
        return page.content, page.html()

    def load_hrefs(self) -> list[str]:
        """Extract all the hrefs from a Wikipedia page

        Returns:
            list[str]: a list of hrefs
        """
        page_html = self.page_html[
                    self.page_html.find(html_page_table_end):self.page_html.find(html_page_references_begin)
                    ]
        hrefs = list(set(re_href.findall(page_html)))
        hrefs = sorted([href.replace('<a href=', "").replace('"', "") for href in hrefs])
        return hrefs

    def get_href(self, href: str) -> Self:
        """Get a WikiPage from a href

        Args:
            href (str): the href to get

        Returns:
            WikiPage: the WikiPage object
        """
        if href in self.hrefs:
            return WikiPage(page_title=href)
        else:
            raise ValueError(f"href {href} not found in {self.page_title} hrefs")


class WikiEvents:
    def __init__(self) -> None:
        """Initialize a WikiEvents object with the date extracted"""
        self.gemini: LLMGemini = LLMGemini(model_name=settings.gemini.GEMINI_WIKI_EVENTS)

    def sort_qualified_events(self, qualified_events: list[QualifiedEvent]) -> list[QualifiedEvent]:
        """Sort the qualified events by the number of criteria identified

        Args:
            qualified_events (list[QualifiedEvent]): the list of qualified events to sort

        Returns:
            list[QualifiedEvent]: the sorted list of qualified events
        """
        nb_criteria = [len(event.identified_criteria) for event in qualified_events]
        argsort = np.argsort(nb_criteria)[::-1]
        return [qualified_events[i] for i in argsort]

    @classmethod
    def get_events_html(cls, date_extracted: tuple[int, int]) -> str:
        """Get the HTML page of the events that happened on the date extracted

        Args:
            date_extracted (tuple[int, int]): the date extracted in the format (month, day)

        Returns:
            str: the HTML page of the events
        """
        month, day = date_extracted
        title = f'{calendar.month_name[month]} {day}'
        page = wikipedia.page(title=title,
                              auto_suggest=False,
                              preload=False).html()

        html_events = page[page.find(html_events_header):page.find(html_births_header)]

        return html_events

    def extract_events(self, html_page: str) -> Events:
        """Extract the events from the HTML page using an LLM

        Args:
            html_page (str): the HTML page

        Returns:
            Events: the events extracted
        """
        response = (
            self.gemini
            .generate_with_structured_output(
                output_type=Events,
                prompt=extract_events.format(html_page=html_page),
                temperature=0
            )
        )
        return response

    def get_events(self, date_extracted: tuple[int, int]) -> Events:
        """Get the events that happened on the date extracted

        Args:
            date_extracted (tuple[int, int], optional): the date extracted in the format (month, day).

        Returns:
            Events: the events that happened on the date extracted
        """
        html_page = self.get_events_html(date_extracted)
        return self.extract_events(html_page)

    def short_summary(self, event: Event) -> tuple[str, list[WikiPage]]:
        """Get a short summary of an event

        Args:
            event (Event): the event to summarize

        Returns:
            str: the short summary of the event
            list[WikiPage]: the Wikipedia pages used to generate the summary
        """
        hrefs = event.hrefs

        chosen_hrefs = (
            self.gemini
            .generate_with_enum(
                enums=hrefs,
                multiple=True,
                prompt=choose_page.format(description=event.description,
                                          pages="\n".join(hrefs)),
                temperature=0
            )
        )

        pages = [WikiPage(page_title=href) for href in set(chosen_hrefs)]

        response = (
            self.gemini
            .generate_from_prompt(
                prompt=short_summary.format(description=event.description,
                                            pages="\n".join([page.page_content for page in pages])),
                temperature=0,
            )
        )

        return response, pages

    def qualify_event(self, event: Event) -> QualifiedEvent:
        """Qualify an event using an LLM

        Args:
            event (Event): the event to qualify

        Returns:
            QualifiedEvent: the qualified event
        """
        summary, pages = self.short_summary(event)

        response = (
            self.gemini
            .generate_with_structured_output(
                output_type=IdentifiedCriteria,
                prompt=qualify_event.format(summary=summary),
                temperature=0,
            )
        )

        return QualifiedEvent(
            event_date=event.event_date,
            description=event.description,
            short_summary=summary,
            pages=pages,
            identified_criteria=response.identified_criteria)

    def qualify_events(self, events: Events) -> list[QualifiedEvent]:
        """Qualify all the events

        Args:
            events (Events): the events to qualify
        """
        qualified_events = []

        def qualify_and_add_event(event: Event) -> None:
            """Qualify an event and add it to the qualified events list

            Args:
                event (Event): the event to qualify
            """
            qualified_event = self.qualify_event(event)
            qualified_events.append(qualified_event)

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(
                tqdm(
                    executor.map(qualify_and_add_event, events.events),
                    total=len(events.events),
                    desc="Parallel qualification of events",
                ),
            )

        self.gemini.print_costs()

        return self.sort_qualified_events(qualified_events)
