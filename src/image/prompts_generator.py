from loguru import logger

from src.config import settings
from src.image.abc_prompts import ABCImagePromptsGenerator, check_and_deduplicate_prompts, check_exhaustivity
from src.gemini import LLMGemini
from src.image.prompts import image_generation_prompt, image_generation_improve_prompt
from src.schemas import ScriptImagePrompts, PromptImproved
from src.scripts.scripts import Script, script_to_string


class PromptsGenerator(ABCImagePromptsGenerator):
    """
    A class to generate prompts for image generation.
    """

    def __init__(self, temperature: int = 0.2):
        """Initialize the PromptsGenerator."""
        super().__init__()

        self.llm = LLMGemini(model_name=settings.gemini.GEMINI_PROMPT_GENERATOR)
        self.temperature = temperature

    def generate_image_prompts(self, script: Script) -> ScriptImagePrompts:
        """Generate image prompts for a given script.

        Args:
            script (Script): The script for which to generate image prompts.

        Returns:
            ScriptImagePrompts: The generated image prompts.
        """
        prompts = self.llm.generate_with_structured_output(
            prompt=image_generation_prompt.format(script=script_to_string(script)),
            output_type=ScriptImagePrompts,
            temperature=self.temperature
        )

        prompts = check_and_deduplicate_prompts(prompts)

        if not check_exhaustivity(script, prompts):
            logger.error("Generated prompts do not cover the whole script. Please check the script and prompts.")

        return prompts

    def modify_image_prompt(self, prompts: ScriptImagePrompts, index: int, comment: str) -> PromptImproved:
        """Generate a new version of the image prompt at the given index.

        Args:
            prompts (ScriptImagePrompts): The current image prompts.
            index (int): The index of the prompt to modify.
            comment (str): What is wrong with the current image.

        Returns:
            ScriptImagePrompts: The modified image prompts.
        """
        new_prompt = self.llm.generate_with_structured_output(
            prompt=image_generation_improve_prompt.format(
                current_images_prompt=str(prompts),
                prompt_to_modify=str(prompts.image_prompts[index]),
                comment=comment
            ),
            output_type=PromptImproved,
            temperature=self.temperature,
        )

        return new_prompt