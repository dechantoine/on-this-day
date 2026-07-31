from abc import ABC

from src.schemas import ImagePrompt, ScriptImagePrompts, Script

class ImageGenerator(ABC):
    """
    Abstract base class for image generation systems.
    """

    def __init__(self):
        """Initialize the image generation system."""
        pass

    @classmethod
    def cost_estimates(cls, prompts: ScriptImagePrompts) -> float:
        """Estimate the number of credits required for the given prompts

        Args:
            prompts (ScriptImagePrompts): The prompts to estimate credits for.

        Returns:
            float: The estimated number of credits.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def generate_images(self, prompts: ScriptImagePrompts, folderpath: str = None):
        """Generate images from the prompts and save them to folderpath.

        Args:
            prompts (ScriptImagePrompts): The prompts to generate images from.
            folderpath (str): The folder path to save the images to.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")