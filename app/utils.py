import datetime
import json
import os

from loguru import logger

from app.schemas import AppHooks, AppScriptImagesPrompts, AppScript, AppEvents, AppQualifiedEvents, AppQualifiedEvent, AppStoryBoards, AppScenesAnimated
from src.config import settings

def create_directory(year:int, month:int, day:int) -> str:
    """Create output directory for the given date if it doesn't exist"""
    date_extracted = datetime.datetime(year=year, month=month, day=day)
    output_dir = f"./prd/{date_extracted.strftime('%Y-%m-%d')}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.success('Created directory structure for date')
    return output_dir

def display_qualified_event(event: AppQualifiedEvent) -> str:
    """Display the selected event"""
    criteria = "\n\n".join([str(criterion) for criterion in event.identified_criteria])

    return f"## {event.description}\n\n{criteria}"

def display_event(event: AppQualifiedEvent) -> str:
    """Display the selected event"""

    return f"## {event.description}\n\n{event.short_summary}"

def init_state() -> dict:
    """Initialize the state of the application."""
    return {
        "date_extracted": None,
        "output_dir": None,
        "events": None,
        "qualified_events": None,
        "chosen_event": None,
        "list_scripts": None,
        "chosen_script": None,
        "enhanced_script": None,
        "list_storyboards": None,
        "image_prompts": None,
        "image_prompt_indices": [],
        "animation_prompts": None,
        "animation_prompt_indices": [],
    }

def load_chosen_script(output_dir: str) -> AppScript:
    """Load the chosen script from the specified output directory.

    Args:
        output_dir (str): The output directory.

    Returns:
        Script: The loaded script.
    """
    file_path = os.path.join(output_dir, settings.app.GENERATED_SCRIPTS_FILENAME)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            scripts = AppHooks(**json.load(f))
            script_index = scripts.selected_script_index
            if script_index:
                return scripts.hooks[script_index[0]].scripts[script_index[1]].script
            else:
                return None
    else:
        raise FileNotFoundError(f"Chosen script file not found: {file_path}")

def load_enhanced_script(output_dir: str) -> AppScript:
    """Load the enhanced script from the specified output directory.

    Args:
        output_dir (str): The output directory.

    Returns:
        Script: The loaded enhanced script.
    """
    file_path = os.path.join(output_dir, settings.app.ENHANCED_TEXT_FILENAME)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return AppScript.model_validate_json(f.read())
    else:
        raise FileNotFoundError(f"Enhanced script file not found: {file_path}")

def load_chosen_event(output_dir) -> AppQualifiedEvent:
    """Load the chosen event from the specified output directory."""
    file_path = os.path.join(output_dir, settings.app.WIKI_CHOSEN_EVENT_FILENAME)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            event_data = json.load(f)
        return AppQualifiedEvent(**event_data)
    else:
        raise FileNotFoundError(f"Chosen event file not found: {file_path}")

def load_storyboards(output_dir) -> AppStoryBoards:
    """Load the storyboards from the specified output directory.

    Args:
        output_dir (str): The output directory.

    Returns:
        AppStoryBoards: The loaded storyboards.
    """
    with open(os.path.join(output_dir, settings.app.GENERATED_STORYBOARD_FILENAME), "r") as f:
        return AppStoryBoards.model_validate_json(f.read())

def load_image_prompts(output_dir) -> AppScriptImagesPrompts:
    """Load the images and their prompts from the specified output directory.

    Args:
        output_dir (str): The output directory.

    Returns:
        AppScriptImagesPrompts: The loaded images and prompts.
    """
    with open(os.path.join(output_dir, settings.app.IMAGES_PROMPTS_FILENAME), "r") as f:
        return AppScriptImagesPrompts.model_validate_json(f.read())

def load_animation_prompts(output_dir) -> AppScenesAnimated:
    """Load the animations and their prompts from the specified output directory.

    Args:
        output_dir (str): The output directory.

    Returns:
        AppScenesAnimated: The loaded animations and their prompts.
    """
    with open(os.path.join(output_dir, settings.app.ANIMATIONS_PROMPTS_FILENAME), "r") as f:
        return AppScenesAnimated.model_validate_json(f.read())

def load_state(year:int, month: int, day: int) -> dict:
    """Load the state from the specified date.

    Args:
        year (int): The year of the event.
        month (int): The month of the event.
        day (int): The day of the event.

    Returns:
        dict: The updated state
    """
    state = init_state()
    state['date_extracted'] = (month, day)
    state['output_dir'] = create_directory(year, month, day)

    # Load Events tab state
    if os.path.exists(os.path.join(state['output_dir'], settings.app.WIKI_EVENTS_FILENAME)):
        with open(os.path.join(state['output_dir'], settings.app.WIKI_EVENTS_FILENAME)) as f:
            state['events'] = AppEvents.model_validate_json(f.read())

    if os.path.exists(os.path.join(state['output_dir'], settings.app.WIKI_EVENTS_QUALIFIED_FILENAME)):
        with open(os.path.join(state['output_dir'], settings.app.WIKI_EVENTS_QUALIFIED_FILENAME), "r") as f:
            state['qualified_events'] = AppQualifiedEvents.model_validate_json(f.read())

    # Load Script tab state
    try:
        state['chosen_event'] = load_chosen_event(state["output_dir"])
    except FileNotFoundError:
        pass
    else:
        # Load candidate hooks if they exist
        if os.path.exists(os.path.join(state['output_dir'], settings.app.GENERATED_SCRIPTS_FILENAME)):
            with open(os.path.join(state['output_dir'], settings.app.GENERATED_SCRIPTS_FILENAME), "r") as f:
                state['list_scripts'] = AppHooks.model_validate_json(f.read())

    # Load Storyboards tab state
    try:
        state['list_storyboards'] = load_storyboards(state["output_dir"])
    except FileNotFoundError:
        pass

    # Load Images tab state
    try:
        state['chosen_script'] = load_chosen_script(state["output_dir"])
        state['enhanced_script'] = load_enhanced_script(state["output_dir"])
    except FileNotFoundError:
        pass
    else:
        # Load image prompts if they exist
        if os.path.exists(os.path.join(state['output_dir'], settings.app.IMAGES_PROMPTS_FILENAME)):
            state['image_prompts'] = load_image_prompts(state["output_dir"])

            # Initialize prompt indices (corresponding to the prompts sliders values)
            state['image_prompt_indices'] = [0] * len(state['image_prompts'].image_prompts)

    try:
        state['animation_prompts'] = load_animation_prompts(state["output_dir"])
    except FileNotFoundError:
        pass

    return state