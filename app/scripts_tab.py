import json
import os

from app.schemas import AppHook, AppHooks, AppGeneratedScript
from src.config import settings
from src.scripts.scripts import ScriptGenerator

script_generator = ScriptGenerator()

def save_state(state: dict) -> None:
    """Save the current state to a file.

    Args:
        state (dict): The current state of the application.
    """
    file_path = os.path.join(state['output_dir'], settings.app.GENERATED_SCRIPTS_FILENAME)
    list_scripts = state['list_scripts']
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(list_scripts.model_dump(mode='json'), f, indent=4)

def generate_candidate_hooks(state: dict, n_hooks: int) -> dict:
    """Generate candidate hooks for the chosen event.

    Args:
        state (dict): The current state of the application.
        n_hooks (int): The number of hooks to generate.

    Returns:
        dict: The updated state with the generated hooks.
    """
    if not state['chosen_event']:
        raise ValueError("No event selected. Please load an event first.")

    hooks = script_generator.generate_hooks(
        event=state['chosen_event'],
        n_hooks=n_hooks,
    )

    if state['list_scripts']:
        for hook in hooks:
            state['list_scripts'].hooks.append(
                AppHook(
                    hook=hook,
                    temperature=script_generator.hook_temperature
                )
            )

    else:
        state['list_scripts'] = AppHooks(
            hooks=[
                AppHook(
                    hook=hook,
                    temperature=script_generator.hook_temperature
                ) for hook in hooks
            ]
        )

    save_state(state)

    return state

def generate_candidate_script(state: dict, index: int) -> dict:
    """Generate candidate script based on the selected hook.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the selected hook.

    Returns:
        dict: The updated state with the generated script.
    """
    script = script_generator.generate_script_from_hook(
        event=state['chosen_event'],
        hook=state['list_scripts'].hooks[index].hook,
    )

    if state['list_scripts'].hooks[index].scripts:
        state['list_scripts'].hooks[index].scripts.append(
            AppGeneratedScript(
                script = script,
                temperature=script_generator.script_temperature
            )
        )

    else:
        state['list_scripts'].hooks[index].scripts = [
            AppGeneratedScript(
                script = script,
                temperature=script_generator.script_temperature
            )
        ]

    save_state(state)

    return state


def display_script(state: dict, script_index: int) -> str:
    """Display the selected script and its associated hook.

    Args:
        state (dict): The current state of the application.
        script_index (int): The index of the selected script.

    Returns:
        str: The formatted string containing the hook and script.
    """
    list_scripts = [
        (script.script, hook.hook) for hook in state['list_scripts'].hooks
        if hook.scripts for script in hook.scripts
    ]
    script = list_scripts[script_index][0]

    return f"{script}"

def select_script(state: dict, script_index: int) -> dict:
    """Select the script at the given index.

    Args:
        state (dict): The current state of the application.
        script_index (int): The index of the script to select.

    Returns:
        dict: The updated state with the selected script index.
    """
    list_scripts = [
        (i, j) for i, hook in enumerate(state['list_scripts'].hooks)
        if hook.scripts for j, _ in enumerate(hook.scripts)
    ]

    state['list_scripts'].selected_script_index = list_scripts[script_index]

    save_state(state)

    return state