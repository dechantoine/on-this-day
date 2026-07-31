import json
import os

from loguru import logger

from app.schemas import AppStoryBoards, AppStoryBoard

from src.config import settings
from src.audio.elevenlabs_tts import ElevenLabsTTS
from src.image.storyboard_generator import StoryboardGenerator

storyboard_generator = StoryboardGenerator()
el = ElevenLabsTTS()

def save_state(state: dict) -> None:
    """Save the state to a file.

    Args:
        state (dict): The state to save.
    """
    if state['enhanced_script'] is not None:
        with open(os.path.join(state['output_dir'], settings.app.ENHANCED_TEXT_FILENAME),
            "w"
        ) as f:
            json.dump(state['enhanced_script'].model_dump(mode='json'), f, indent=4)

    if state['list_storyboards'] is not None:
        with open(os.path.join(state['output_dir'], settings.app.GENERATED_STORYBOARD_FILENAME),
            "w"
        ) as f:
            json.dump(state['list_storyboards'].model_dump(mode='json'), f, indent=4)


def storyboard_to_markdown(storyboard: AppStoryBoard) -> str:
    """
    Transforms a StoryBoard object into a Markdown table string.

    Args:
        storyboard: The StoryBoard object to convert.

    Returns:
        A string formatted as a Markdown table.
    """
    # Initialize the table with headers
    markdown_table = [
        "| Scene # | Script Segment | Visual Description |",
        "|:-------:|:---------------|:-------------------|",
    ]

    # Populate the table with scene data
    for i, scene in enumerate(storyboard.scenes):
        # Clean up newlines within the text to prevent table breaking
        script = scene.script_segment.replace('\n', ' ').strip()
        description = (
            scene.visual_description
            .replace('\n', ' ')
            .replace('<', '\<')
            .replace('>', '\>')
        ).strip()

        row = f"| {i + 1} | {script} | {description} |"
        markdown_table.append(row)

    return "\n".join(markdown_table)

def generate_storyboards(state: dict) -> dict:
    """Generate storyboards from the chosen script and update the state.

    Args:
        state (dict): The current state of the application.

    Returns:
        dict: The updated state with the generated image prompts.
    """
    logger.info("Generating storyboards")

    if not state['chosen_script']:
        raise ValueError("No script selected. Please load a script first.")

    if not state['enhanced_script']:
        state['enhanced_script'] = el.text_enhancer.add_audio_tags(state['chosen_script'])
        save_state(state)

    storyboards = storyboard_generator.generate_storyboards(
        script=state['enhanced_script'].clean_audio_tags(),
    )

    # convert to AppStoryBoards
    state['list_storyboards'] = AppStoryBoards(
        storyboards=storyboards.storyboards,
        selected_storyboard_index=None,
        lookbook=None
    )

    # save the state
    save_state(state)

    return state

def select_storyboard(state: dict, storyboard_index: int) -> dict:
    """Select the storyboard at the given index and update the state.

    Args:
        state (dict): The current state of the application.
        storyboard_index (int): The index of the storyboard to select.

    Returns:
        dict: The updated state with the selected storyboard.
    """
    state['list_storyboards'].selected_storyboard_index = storyboard_index

    save_state(state)

    return state