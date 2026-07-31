import os

from google.genai import Client, errors, types
from loguru import logger
from tqdm import tqdm

from src.config import settings
from src.image.abc_image import ImageGenerator
from src.schemas import ScriptImagePrompts

models_pricing = {
    'imagen-4.0-generate-preview-06-06': 0.04,
    'imagen-4.0-fast-generate-preview-06-06': 0.02,
    'imagen-4.0-ultra-generate-preview-06-06': 0.06,
}

class Imagen(ImageGenerator):
    """
    Class for generating images using Google's Imagen.
    """

    def __init__(self):
        """Initialize the Imagen image generation system."""
        super().__init__()
        self.project = settings.gcp.imagen.PROJECT_ID
        self.location = settings.gcp.imagen.LOCATION_ID
        self.model_name = settings.gcp.imagen.MODEL_NAME

        self.client = Client(
            vertexai=True,
            project=self.project,
            location=self.location,
        )
        self.number_of_images = settings.gcp.imagen.NUMBER_OF_IMAGES
        self.default_folderpath = settings.gcp.imagen.DEFAULT_FOLDERPATH
        self.aspect_ratio = settings.gcp.imagen.ASPECT_RATIO
        self.safety_filter_level = settings.gcp.imagen.SAFETY_FILTER_LEVEL
        self.guidance_scale = settings.gcp.imagen.GUIDANCE_SCALE
        self.person_generation = settings.gcp.imagen.PERSON_GENERATION
        self.image_prompt_language = settings.gcp.imagen.IMAGE_PROMPT_LANGUAGE
        self.enhance_prompt = settings.gcp.imagen.ENHANCE_PROMPT


        try:
            self.client.models.get(model=self.model_name)
        except errors.ClientError:
            logger.error(f"Model {self.model_name} not found in project {self.project} at location {self.location}")
            raise

        logger.info(
            f"Imagen initialized with model {self.model_name}"
            f" in project {self.project} at location {self.location}"
        )

    def cost_estimates(self, prompts: ScriptImagePrompts) -> float:
        """Estimate the number of credits required for the given prompts.

        Args:
            prompts (ScriptImagePrompts): The prompts to estimate the cost for.
        """
        return self.number_of_images * models_pricing[self.model_name] * len(prompts.image_prompts)

    def generate_images(self, prompts: ScriptImagePrompts, folderpath=None):
        """Generate images from the prompts and save them to folderpath.

        Args:
            prompts (ScriptImagePrompts): The prompts to generate images from.
            folderpath (str): The folder path to save the images to. Defaults to "generated_images".

        """
        if folderpath is None:
            folderpath = self.default_folderpath

        if folderpath and not os.path.exists(folderpath):
            os.makedirs(folderpath)

        for i, image_prompt in tqdm(enumerate(prompts.image_prompts), desc="Generating images"):
            response = None
            try:
                response = self.client.models.generate_images(
                    model=self.model_name,
                    prompt=image_prompt.prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=self.number_of_images,
                        negative_prompt=image_prompt.negative_prompt,
                        aspect_ratio=self.aspect_ratio,
                        safety_filter_level=types.SafetyFilterLevel(
                            self.safety_filter_level
                        ),
                        guidance_scale=self.guidance_scale,
                        include_rai_reason=True,
                        output_mime_type='image/jpeg',
                        person_generation=types.PersonGeneration(
                            self.person_generation
                        ),
                        language=types.ImagePromptLanguage(
                            self.image_prompt_language
                        ),
                        enhance_prompt=self.enhance_prompt,
                    )
                )
                image_data = response.generated_images[0].image
                image_data.save(f"{folderpath}/{i}.png")

            except Exception as e:
                logger.error(f"Error generating image for prompt '{image_prompt.prompt}': {e}\nmodel response: {response}")