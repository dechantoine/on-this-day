import json
import os

from loguru import logger

from app.schemas import AppQualifiedEvents
from src.config import settings
from src.scripts.wiki import WikiEvents

events_extractor = WikiEvents()

def save_state(state: dict) -> None:
    """Save the current state to a file.

    Args:
        state (dict): The current state of the application.
    """
    file_path = os.path.join(state['output_dir'], settings.app.WIKI_EVENTS_FILENAME)
    list_events = state['events']
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(list_events.model_dump(mode='json'), f, indent=4)

    if state['qualified_events']:
        file_path = os.path.join(state['output_dir'], settings.app.WIKI_EVENTS_QUALIFIED_FILENAME)
        list_qualified_events = state['qualified_events']
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(list_qualified_events.model_dump(mode='json'), f, indent=4)

def get_events(state: dict) -> dict:
    """Get and process wiki events for the given date"""
    if not state['events']:
        logger.info(f"No events found for {state['date_extracted']}, extracting from Wikipedia...")
        events = events_extractor.get_events(state['date_extracted'])
        state['events'] = events
        save_state(state)

    logger.info(f"Found {len(state['events'].events)} events for {state['date_extracted']}, qualifying...")
    qualified_events = events_extractor.qualify_events(state['events'])
    state['qualified_events'] = AppQualifiedEvents(qualified_events=qualified_events)
    save_state(state)

    return state


def select_and_save_event(state: dict, event_index: int) -> dict:
    """Select and save the chosen event

    Args:
        state (dict): The current state of the application.
        event_index (int): The index of the selected event.

    Returns:
        dict: The updated state with the chosen event.
    """
    state['chosen_event'] = state['qualified_events'].qualified_events[event_index]

    # save the chosen event to file
    file_path = os.path.join(state['output_dir'], settings.app.WIKI_CHOSEN_EVENT_FILENAME)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(state['chosen_event'].model_dump(mode='json'), f, indent=4)

    return state