import abc
from calendar import month_name
from enum import Enum
import re
from typing import Self

from pydantic import BaseModel, Field, create_model

audio_tag_pattern = r'\[.*?\]\s?'

class EventDate(BaseModel):
    year: int = Field(..., title="Year of the event (can be negative)")
    month: int = Field(..., title="Month of the event")
    day: int = Field(..., title="Day in the month")

    def __str__(self):
        return f"{self.day}, {month_name[self.month]} {self.year}"

class Event(BaseModel):
    event_date: EventDate
    description: str = Field(..., title="Description of the event")
    hrefs: list[str] = Field(..., title="All the links related to the event")


class Events(BaseModel):
    events: list[Event] = Field(..., title="List of events")


class Page(BaseModel, abc.ABC):
    page_title: str = Field(..., title="Title of the Wikipedia page")
    page_content: str = Field(..., title="Content of the Wikipedia page")
    page_html: str = Field(..., title="HTML content of the Wikipedia page")
    hrefs: list[str] = Field(..., title="All the links related to the Wikipedia page")


class ChosenPages(BaseModel):
    pages: list[str] = Field(..., title="List of href pages")


class Criterion(str, Enum):
    controversial_events = "Controversial events"
    tragic_catastrophic_events = "Tragic & Catastrophic Events"
    revolutionary_discoveries_innovations = "Revolutionary Discoveries & Innovations"
    wars_conflicts_revolutions = "Wars, Conflicts & Revolutions"
    crime_heists = "Crime & Heists"
    political_social_movements = "Political & Social Movements"
    firsts_in_history = "Firsts in History"
    pop_culture_entertainment_milestones = "Pop Culture & Entertainment Milestones"
    iconic_figures_legends = "Iconic Figures & Legends"


class IdentifiedCriterion(BaseModel):
    criterion: Criterion = Field(..., title="Identified Criterion")
    information: str = Field(..., title="Information that led to the identification of the criterion")

    def __str__(self):
        return f"{self.criterion.value}: {self.information}"


class IdentifiedCriteria(BaseModel):
    identified_criteria: list[IdentifiedCriterion] = Field(..., title="List of identified criteria")


class QualifiedEvent(BaseModel):
    event_date: EventDate
    description: str = Field(..., title="Description of the event")
    short_summary: str = Field(..., title="Extended summary of the event")
    pages: list[Page] = Field(..., title="List of Wikipedia pages")
    identified_criteria: list[IdentifiedCriterion] = Field(..., title="List of identified criteria")

class QualifiedEvents(BaseModel):
    qualified_events: list[QualifiedEvent] = Field(..., title="List of qualified events")

def create_hooks_model(model_name: str, num_hooks: int) -> BaseModel:
    """Create a model with a dynamic number of hooks."""
    return create_model(
        model_name,
        **{f"hook_{i}": (str, ...) for i in range(num_hooks)}
    )


class Script(BaseModel):
    title: str = Field(
        ...,
        title="Title of the video",
        description="This should be a catchy title that will attract the audience."
    )
    hook: str = Field(
        ...,
        title="Hook of the video.",
        description="This is a one sentence engaging introduction that will grab the audience's attention."
                    " It should be a question or a statement related to what will follow and that makes the audience curious."
    )
    context : str = Field(
        ...,
        title="Context of the script",
        description="This set the stage for the story."
                    " It must begin exactly with 'On this day, <MONTH> <DAY>, <YEAR>,' and include the exact date of the event."
                    " It must exactly tell about the precise event that happened on that date."
                    " Up to 3 sentences."
    )
    rising_tension: str = Field(
        ...,
        title="Rising tension of the video",
        description="This builds the story and describes the events leading up to the climax."
                    " It should include all relevant characters and their motivations."
                    " Up to 2 sentences."
    )
    climax: str = Field(
        ...,
        title="Climax of the script",
        description="This is the reveal of the story."
                    " Everything should lead to this moment."
                    "Emphasize the most important part of the story."
                    " Up to 3 sentences."

    )
    conclusion: str = Field(
        ...,
        title="Conclusion of the video",
        description="This is the conclusion of the story."
                    " It should include the consequences of the event, its impact on the world/country/region or society/people, etc."
                    " It should also talk about the legacy of the event."
                    " Up to 2 sentences."
    )

    def __str__(self):
        return (
            f"**Title**: {self.title}\n\n"
            f"**Hook**: {self.hook}\n\n"
            f"**Context**: {self.context}\n\n"
            f"**Rising Tension**: {self.rising_tension}\n\n"
            f"**Climax**: {self.climax}\n\n"
            f"**Conclusion**: {self.conclusion}\n\n"
        )

    def clean_audio_tags(self) -> Self:
        """Remove all audio tags from the script"""
        return Script(
            title=self.title,
            hook=re.sub(audio_tag_pattern, '', self.hook).strip(),
            context=re.sub(audio_tag_pattern, '', self.context).strip(),
            rising_tension=re.sub(audio_tag_pattern, '', self.rising_tension).strip(),
            climax=re.sub(audio_tag_pattern, '', self.climax).strip(),
            conclusion=re.sub(audio_tag_pattern, '', self.conclusion).strip(),
        )


class SpeechAdapter(BaseModel):
    original_text: str = Field(..., title="Original text")
    adapted_text: str = Field(..., title="Adapted text")


class SpeechAdaptersList(BaseModel):
    adapters: list[SpeechAdapter] = Field(..., title="List of speech adapters")


class SplittedSentences(BaseModel):
    sentences: list[str]

    @classmethod
    def clean_audio_tags(cls, sentences: list[str]) -> list[str]:
        """Remove all audio tags from the sentences

        Args:
            sentences (list[str]): List of sentences with audio tags

        Returns:
            list[str]: List of sentences without audio tags
        """
        sentences_clean = [re.sub(audio_tag_pattern, '', sentence).strip() for sentence in sentences]
        return sentences_clean


class CutInfo(BaseModel):
    cut_time: float = Field(...,description="The start time of the cut in seconds, relative to the original audio timeline.")
    cut_duration: float = Field(...,description="The duration of the cut in seconds.")


class CutAudio(BaseModel):
    raw_filepath: str = Field(..., title="Path to the raw audio file")
    cut_filepath: str = Field(..., title="Path to the cut audio file")
    raw_audio_duration: float = Field(..., title="Duration of the audio file in seconds")
    cuts: list[CutInfo] = Field(..., title="List of cuts applied to the audio file")


class CutAudioList(BaseModel):
    audios: list[CutAudio] = Field(..., title="List of cut audio files")


class TextAligned(BaseModel):
    text: str = Field(..., title="Text aligned")
    start_time: float = Field(..., title="Start time of the text in seconds")
    end_time: float = Field(..., title="End time of the text in seconds")


class TextsAlignedList(BaseModel):
    texts: list[TextAligned] = Field(..., title="List of texts with their start and end times")


class ImageAligned(BaseModel):
    text: str = Field(..., title="Text aligned with the image")
    path: str = Field(..., title="Path of the image")
    start_time: float = Field(..., title="Start time of the image in seconds")
    end_time: float = Field(..., title="End time of the image in seconds")
    duration: float = Field(..., title="Duration of the image in seconds")

VideoAligned = ImageAligned

class Scene(BaseModel):
    script_segment: str = Field(..., description="The segment of the script for this scene.")
    visual_description: str = Field(
        ...,
        description="A vivid description of the on-screen action, characters, and setting for this scene."
                    " This should include named entities for recurring elements (e.g., <Character Name>, <Object Name>)."
    )

    def __str__(self):
        return (f"**Script Segment**: {self.script_segment}\n\n"
                f"**Visual Description**: {self.visual_description}")

class StoryBoard(BaseModel):
    scenes: list[Scene] = Field(..., description="A list of scenes that make up the storyboard.")

    def __str__(self):
        return "\n\n".join([f"### Scene {i}:\n\n {str(scene)}" for i, scene in enumerate(self.scenes)])

class StoryBoards(BaseModel):
    storyboards: list[StoryBoard] = Field(..., description="A list of distinct storyboards for the same script.")

class CharacterDescription(BaseModel):
    name: str = Field(..., description="The unique name of the character (e.g., '<General Petrov>').")
    appearance: str = Field(..., description="Detailed physical description: age, hair color/style, key facial features.")
    attire: str = Field(..., description="Detailed description of their primary outfit, referencing historical accuracy.")

    def __str__(self):
        return f"**Name**: {self.name}\n\n**Appearance**: {self.appearance}\n\n**Attire**: {self.attire}\n\n"

class LocationDescription(BaseModel):
    name: str = Field(..., description="The unique name of the location (e.g., '<The Rebel Hideout>').")
    architecture_style: str = Field(..., description="Description of the setting's architecture and style.")
    lighting_atmosphere: str = Field(..., description="Description of the lighting and overall mood of the location.")

    def __str__(self):
        return f"**Name**: {self.name}\n\n**Architecture/Style**: {self.architecture_style}\n\n**Lighting/Atmosphere**: {self.lighting_atmosphere}\n\n"

class ObjectDescription(BaseModel):
    name: str = Field(..., description="The unique name of the object (e.g., '<The Secret Treaty>').")
    description: str = Field(..., description="A detailed description of the prop.")

    def __str__(self):
        return f"**Name**: {self.name}\n\n**Description**: {self.description}\n\n"

class VisualLookbook(BaseModel):
    mood_color_palette: str = Field(..., description="The dominant visual tone and color scheme for the entire video.")
    characters: list[CharacterDescription] = Field(..., description="A list of all recurring characters.")
    locations: list[LocationDescription] = Field(..., description="A list of all key locations.")
    objects: list[ObjectDescription] = Field(..., description="A list of all important recurring objects.")

    def __str__(self) -> str:
        return (
            f"### Mood/Color Palette\n\n {self.mood_color_palette}\n\n"
            f"### Characters\n\n" + "\n".join([f"- {str(character)}" for character in self.characters]) + "\n\n"
            f"### Locations\n\n" + "\n".join([f"- {str(location)}" for location in self.locations]) + "\n\n"
            f"### Objects\n\n" + "\n".join([f"- {str(obj)}" for obj in self.objects]) + "\n\n"
        )

class ImagePrompt(BaseModel):
    prompt: str = Field(..., description="The prompt to generate the image with Imagen to display with this script segment.")
    script_segment: str = Field(..., description="The script segment.")
    negative_prompt: str | None = Field(
        description="The negative prompt to generate the image with Imagen to display with this script segment.",
        default=None)

    def __str__(self):
        return (
            f"**Script Segment**: {self.script_segment}\n"
            f"**Prompt**: {self.prompt}\n"
            f"**Negative Prompt**: {self.negative_prompt}"
        )

class ScriptImagePrompts(BaseModel):
    image_prompts: list[ImagePrompt]

    def __str__(self):
        return "\n\n".join([f"{i}:\n {str(prompt)}" for i, prompt in enumerate(self.image_prompts)])

class PromptImproved(BaseModel):
    prompt: str = Field(..., description="The improved prompt to generate the image with Imagen to display with this script segment.")
    negative_prompt: str = Field(..., description="The negative prompt to generate the image with Imagen to display with this script segment.")

class SceneIllustrated(Scene):
    prompt: str = Field(..., description="The prompt used to generate the first image of this scene with Imagen.")
    negative_prompt: str = Field(..., description="The negative prompt used to generate the first image of this scene with Imagen.")

    def __str__(self):
        return (f"**Script Segment**: {self.script_segment}\n\n"
                f"**Visual Description**: {self.visual_description}\n\n"
                f"**Prompt**: {self.prompt}\n\n"
                f"**Negative Prompt**: {self.negative_prompt}\n\n")

class ScenesIllustrated(BaseModel):
    scenes: list[SceneIllustrated]

class SceneAnimated(BaseModel):
    script_segment: str = Field(..., description="The segment of the script for this scene.")
    animation_prompt: str = Field(..., description="The prompt to animate the image of this script segment with an image-to-video model.")

class ScenesAnimated(BaseModel):
    scenes: list[SceneAnimated]

class EnhancedScript(Script):
    title: str = Field(
        description="The exact same title of the video.",
    )
    hook: str = Field(
        description="The exact same hook but enhanced with audio tags for better TTS rendering.",
    )
    context : str = Field(
        description="The exact same context of the video but enhanced with audio tags for better TTS rendering.",
    )
    rising_tension: str = Field(
        description="The exact same rising tension of the video but enhanced with audio tags for better TTS rendering.",
    )
    climax: str = Field(
        description="The exact same climax of the video but enhanced with audio tags for better TTS rendering.",
    )
    conclusion: str = Field(
        description="The exact same conclusion of the video but enhanced with audio tags for better TTS rendering.",
    )