import re

from loguru import logger
from tqdm import tqdm

from src.config import settings
from src.image.abc_prompts import ABCImagePromptsGenerator
from src.gemini import LLMGemini
from src.image.prompts import (
    draft_video_flows_prompt,
    describe_video_components_prompt,
    extract_schema_prompt,
    generate_image_prompt,
    generate_better_image_prompt,
    generate_animation_prompt
)
from src.schemas import (
    ImagePrompt,
    Scene,
    StoryBoard,
    StoryBoards,
    VisualLookbook,
    ScriptImagePrompts,
    PromptImproved,
    ScenesIllustrated,
    SceneAnimated,
    ScenesAnimated
)
from src.scripts.scripts import Script, script_to_string


class StoryboardGenerator(ABCImagePromptsGenerator):
    """
    A class to generate prompts for image generation.
    """

    def __init__(self, temperature: int = 0.2):
        """Initialize the StoryboardGenerator."""
        super().__init__()

        self.llm = LLMGemini(model_name=settings.gemini.GEMINI_STORYBOARD_GENERATOR)
        self.temperature = temperature

    @staticmethod
    def extract_visual_elements(scene: Scene, lookbook: VisualLookbook) -> VisualLookbook:
        """Finds all named entities (e.g., <Entity Name>) in a scene's descriptions
        and creates a new, filtered lookbook containing only the details for those entities.

        Args:
            scene: The Scene object to be analyzed.
            lookbook: The complete VisualLookbook for the entire video.

        Returns:
            A new VisualLookbook instance containing only the elements relevant to the scene.
        """
        # Combine the script and visual description to search for entities in both
        text_to_search = scene.script_segment + " " + scene.visual_description

        # Find all unique named entities in the combined text
        found_entities = set(re.findall(r"(<[^>]+>)", text_to_search))

        if not found_entities:
            # Return a lookbook with just the mood if no specific entities are mentioned
            return VisualLookbook(mood_color_palette=lookbook.mood_color_palette, characters=[], locations=[],
                                  objects=[])

        # Create and return the new, filtered lookbook
        return VisualLookbook(
            mood_color_palette=lookbook.mood_color_palette,
            characters=[char for char in lookbook.characters if char.name in found_entities],
            locations=[loc for loc in lookbook.locations if loc.name in found_entities],
            objects=[obj for obj in lookbook.objects if obj.name in found_entities]
        )

    def generate_storyboards(self, script: Script) -> StoryBoards:
        """Generate storyboards for a given script.

        Args:
            script (Script): The script for which to generate storyboards.

        Returns:
            StoryBoards: The generated storyboards.
        """
        str_script = script_to_string(script)

        storyboards = self.llm.generate_with_structured_output(
            prompt=draft_video_flows_prompt.format(script=str_script),
            output_type=StoryBoards,
            temperature=self.temperature
        )

        # reorder scenes to be in script order
        for storyboard in storyboards.storyboards:
            ordered_scenes = []
            original_len = len(storyboard.scenes)
            str_script = script_to_string(script).strip()
            it = 0
            while it < original_len:
                for scene in storyboard.scenes:
                    if str_script.startswith(scene.script_segment.strip()):
                        ordered_scenes.append(scene)
                        storyboard.scenes.remove(scene)
                        str_script = str_script.replace(scene.script_segment, "").strip()
                        break
                it += 1

            if len(ordered_scenes) != original_len:
                logger.warning("Could not reorder all scenes correctly.")
            storyboard.scenes = ordered_scenes

        return storyboards

    def generate_lookbook(self, storyboard: StoryBoard) -> VisualLookbook:
        """Generate a visual lookbook for a given storyboard.

        Args:
            storyboard (StoryBoard): The storyboard for which to generate a lookbook.

        Returns:
            VisualLookbook: The generated visual lookbook.
        """
        str_lookbook = self.llm.generate_with_grounding(
            prompt=describe_video_components_prompt.format(storyboard=str(storyboard), visual_lookbook=VisualLookbook.model_json_schema()),
        ).candidates[0].content.parts[0]

        lookbook = self.llm.generate_with_structured_output(
            prompt=extract_schema_prompt.format(output=str_lookbook),
            output_type=VisualLookbook,
            temperature=0
        )

        return lookbook

    def generate_image_prompts(self,
                               storyboard: StoryBoard,
                               lookbook: VisualLookbook
                               ) -> ScriptImagePrompts:
        """Generate image prompts for a given script.

        Args:
            storyboard (StoryBoard): The storyboard for which to generate a prompts.
            lookbook (VisualLookbook): The lookbook guiding the style of the prompts.

        Returns:
            ScriptImagePrompts: The generated image prompts.
        """
        prompts = ScriptImagePrompts(image_prompts=[])

        for scene in tqdm(iterable=storyboard.scenes, desc="Generating images prompts"):
            filtered_lookbook = self.extract_visual_elements(scene, lookbook)
            prompt = generate_image_prompt.format(
                script_segment=scene.script_segment,
                scene_visual_description=scene.visual_description,
                visual_lookbook=str(filtered_lookbook)
            )

            scene_prompt = self.llm.generate_with_structured_output(
                prompt=prompt,
                output_type=ImagePrompt,
                temperature=self.temperature
            )

            scene_prompt.script_segment = scene.script_segment

            prompts.image_prompts.append(scene_prompt)

        return prompts

    def modify_image_prompt(self,
                            storyboard: StoryBoard,
                            lookbook: VisualLookbook,
                            prompts: ScriptImagePrompts,
                            index: int,
                            comment: str
                            ) -> PromptImproved:
        """Generate a new version of the image prompt at the given index.

        Args:
            storyboard (StoryBoard): The storyboard for which to generate a prompts.
            lookbook (VisualLookbook): The lookbook guiding the style of the prompts.
            prompts (ScriptImagePrompts): The current image prompts.
            index (int): The index of the prompt to modify.
            comment (str): What is wrong with the current image.

        Returns:
            ScriptImagePrompts: The modified image prompts.
        """
        for s_scene in storyboard.scenes:
            if s_scene.script_segment == prompts.image_prompts[index].script_segment:
                filtered_lookbook = self.extract_visual_elements(s_scene, lookbook)
                scene = s_scene

        new_prompt = self.llm.generate_with_structured_output(
            prompt=generate_better_image_prompt.format(
                scene_visual_description=scene.visual_description,
                visual_lookbook=str(filtered_lookbook),
                original_prompt=str(prompts.image_prompts[index]),
                comment=comment
            ),
            output_type=PromptImproved,
            temperature=self.temperature,
        )

        return new_prompt

    def generate_animation_prompts(
            self,
            scenes: ScenesIllustrated
    ) -> ScenesAnimated:
        """Generate prompts to animate the first image of each scene.

        Args:
            scenes (ScenesIllustrated): The scenes to animate.

        Returns:
            ScenesAnimated: The generated animated scene prompts.
        """
        prompts = ScenesAnimated(
            scenes=[]
        )

        for scene in tqdm(iterable=scenes.scenes, desc="Generating animation prompts"):
            prompt = generate_animation_prompt.format(
                scene_to_animate=scene.visual_description,
                image_prompt=scene.prompt,
                image_negative_prompt=scene.negative_prompt,
            )

            animation_prompt = self.llm.generate_with_structured_output(
                prompt=prompt,
                output_type=SceneAnimated,
                temperature=self.temperature
            )

            animation_prompt.script_segment = scene.script_segment

            prompts.scenes.append(animation_prompt)

        return prompts
