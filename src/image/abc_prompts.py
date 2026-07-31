from loguru import logger

from src.schemas import ScriptImagePrompts, PromptImproved
from src.scripts.scripts import Script, script_to_string



def check_and_deduplicate_prompts(prompts: ScriptImagePrompts) -> ScriptImagePrompts:
    """Check and deduplicate image prompts.

    Args:
        prompts (ScriptImagePrompts): The image prompts to check.

    Returns:
        ScriptImagePrompts: The deduplicated image prompts.
    """
    if len(set(image_prompt.script_segment for image_prompt in prompts.image_prompts)) < len(prompts.image_prompts):
        logger.warning("Some script segments are duplicated. Deduplicating them.")
        seen_segments = set()
        unique_prompts = []
        for image_prompt in prompts.image_prompts:
            if image_prompt.script_segment not in seen_segments:
                seen_segments.add(image_prompt.script_segment)
                unique_prompts.append(image_prompt)
        prompts.image_prompts = unique_prompts

    return prompts


def check_exhaustivity(script: Script, prompts: ScriptImagePrompts) -> bool:
    """
    Check if the generated prompts cover all script segments.
    Args:
        script (Script): The script to check against.
        prompts (ScriptImagePrompts): The generated image prompts.
    """
    script_string = script_to_string(script)
    prompt_string = " ".join([image_prompt.script_segment for image_prompt in prompts.image_prompts])

    if script_string != prompt_string:
        return False

    return True

class ABCImagePromptsGenerator:
    """
    A class to generate prompts for image generation.
    """

    def __init__(self, temperature:int = 0.2):
        """Initialize the PromptsGenerator."""
        pass

    def generate_image_prompts(self,
                               *args) -> ScriptImagePrompts:
        """Generate image prompts for a given script.

        Returns:
            ScriptImagePrompts: The generated image prompts.
        """
        pass

    def modify_image_prompt(self, prompts: ScriptImagePrompts, index: int, comment: str) -> PromptImproved:
        """Generate a new version of the image prompt at the given index.

        Args:
            prompts (ScriptImagePrompts): The current image prompts.
            index (int): The index of the prompt to modify.
            comment (str): What is wrong with the current image.

        Returns:
            ScriptImagePrompts: The modified image prompts.
        """
        pass