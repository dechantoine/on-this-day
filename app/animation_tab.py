import json
import os

from app.schemas import AppScenesIllustrated

from src.config import settings
from src.image.storyboard_generator import StoryboardGenerator

storyboard_generator = StoryboardGenerator()

def save_state(state: dict) -> None:
    """Save the state to a file.

    Args:
        state (dict): The state to save.
    """
    if state['animation_prompts'] is not None:
        with open(os.path.join(state['output_dir'], settings.app.ANIMATIONS_PROMPTS_FILENAME),
            "w"
        ) as f:
            json.dump(state['animation_prompts'].model_dump(mode='json'), f, indent=4)

def generate_animations(state: dict) -> dict:
    """Generate animations based on a state.

    Args:
        state (dict): The state to generate animations for.

    Returns:
        dict: The state with animations generated.
    """
    animations_folder = os.path.join(state['output_dir'], settings.app.ANIMATIONS_FOLDER)
    if not os.path.exists(animations_folder):
        os.makedirs(animations_folder)

    storyboard = state['list_storyboards'].storyboards[state['list_storyboards'].selected_storyboard_index]
    scenes = AppScenesIllustrated.from_storyboard_image_prompts(
        storyboard=storyboard,
        image_prompts=state['image_prompts'],
    )

    animations = storyboard_generator.generate_animation_prompts(
        scenes=scenes,
    )

    state['animation_prompts'] = animations

    save_state(state)

    return state