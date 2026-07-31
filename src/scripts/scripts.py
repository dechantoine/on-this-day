from loguru import logger

from src.config import settings
from src.gemini import LLMGemini
from src.scripts.prompts import script_hooks, script_full
from src.schemas import Page, QualifiedEvent, Script, create_hooks_model

def script_to_string(script: Script) -> str:
    """Convert a Script object to a string representation.

    Args:
        script (Script): The Script object to convert.
    """
    return " ".join([value for key, value in script if key != 'title'])


class ScriptGenerator:
    def __init__(self,
                 hook_temperature: float = 0.7,
                 script_temperature: float = 0.7,
                 ):
        self.gemini = LLMGemini(model_name=settings.gemini.GEMINI_SCRIPT_GENERATOR)
        self.hook_temperature = hook_temperature
        self.script_temperature = script_temperature

    def format_pages(self, pages: list[Page]) -> str:
        """Format the Wikipedia pages for the prompt.

        Args:
            event (list[Page]): The list of Wikipedia pages related to the event.
        """
        return "".join(
            f"Page title: {page.page_title}\nPage content:{page.page_content}\n\n" for page in pages
        )

    def generate_hooks(self, event: QualifiedEvent, n_hooks: int) -> list[str]:
        """Generate hooks for a given event.

        Args:
            event (QualifiedEvent): The event for which to generate hooks.
            n_hooks (int): The number of hooks to generate.
        """
        hooks_model = create_hooks_model("ListHooks", n_hooks)

        pages_formatted = self.format_pages(event.pages)

        hooks = self.gemini.generate_with_structured_output(
            prompt=script_hooks.format(description=event.description, pages=pages_formatted),
            output_type=hooks_model,
            temperature=self.hook_temperature,
        )

        return list(dict(hooks).values())

    def generate_script_from_hook(self, event: QualifiedEvent, hook: str) -> Script:
        """Generate a script for a given event and hook.

        Args:
            event (QualifiedEvent): The event for which to generate the script.
            hook (str): The hook to use for the script.
        """
        pages_formatted = self.format_pages(event.pages)

        script = self.gemini.generate_with_structured_output(
            prompt=script_full.format(date=str(event.event_date),
                                      hook=hook,
                                      pages=pages_formatted),
            output_type=Script,
            temperature=self.script_temperature,
        )

        return script

    def generate_scripts(self,
                         event: QualifiedEvent,
                         n_hooks: int | None = None,
                         hooks: list[str] | None = None,
                         ) -> list[Script]:
        """Generate scripts for a given event and hooks. Either generates new hooks or uses provided hooks.

        Args:
            event (QualifiedEvent): The event for which to generate scripts.
            n_hooks (int): The number of hooks to generate scripts for.
            hooks (list[str]): A list of hooks to use for script generation.
        """
        if n_hooks and not hooks:
            hooks = self.generate_hooks(event, n_hooks)
            logger.info(f"Hooks generated: {hooks}")
        if not n_hooks and not hooks:
            raise ValueError("Either n_hooks or hooks must be provided.")

        scripts = []
        for hook in hooks:
            script = self.generate_script_from_hook(event, hook)
            scripts.append(script)
        return scripts