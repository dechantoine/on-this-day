import json
import os

import gradio as gr
from loguru import logger
from tqdm import tqdm

from app.schemas import AppSrcScriptImagePrompts, AppSrcImagePrompt, AppScriptImagesPrompts, AppImagesPrompts, AppImagePrompt
from src.config import settings
from src.image.storyboard_generator import StoryboardGenerator
from src.image.imagen import Imagen

storyboard_generator = StoryboardGenerator()
image_generator = Imagen()

def save_state(state: dict) -> None:
    """Save the state to a file.

    Args:
        state (dict): The state to save.
    """
    if state['list_storyboards'] is not None:
        with open(os.path.join(state['output_dir'], settings.app.GENERATED_STORYBOARD_FILENAME),
            "w"
        ) as f:
            json.dump(state['list_storyboards'].model_dump(mode='json'), f, indent=4)

    if state['image_prompts'] is not None:
        with open(
            os.path.join(state['output_dir'], settings.app.IMAGES_PROMPTS_FILENAME),
            "w"
        ) as f:
            json.dump(state['image_prompts'].model_dump(mode='json'), f, indent=4)

def generate_image_prompts(state: dict) -> dict:
    """Generate image prompts for the chosen script.

    Args:
        state (dict): The current state of the application.

    Returns:
        dict: The updated state with the generated image prompts.
    """
    if not state['list_storyboards']:
        raise ValueError("No storyboard generated yet. Please generate a storyboard first.")

    chosen_storyboard = state['list_storyboards'].storyboards[state['list_storyboards'].selected_storyboard_index]

    logger.info("Generating lookbook...")
    lookbook = storyboard_generator.generate_lookbook(
        storyboard=chosen_storyboard
    )

    state['list_storyboards'].lookbook = lookbook

    save_state(state)

    logger.info(f"Generating image prompts...")
    prompts = storyboard_generator.generate_image_prompts(
        storyboard=chosen_storyboard,
        lookbook=lookbook,
    )

    # convert to AppScriptImagesPrompts
    state['image_prompts'] = AppScriptImagesPrompts.from_script_image_prompts(prompts)

    # save the AppScriptImagesPrompts to file
    save_state(state)

    # initialize prompt indices (corresponding to the prompts sliders values)
    state['image_prompt_indices'] = [0] * len(prompts.image_prompts)

    return state

def generate_all_images(state: dict) -> dict:
    """Generate images for all image prompts.

    Args:
        state (dict): The current state of the application.

    Returns:
        dict: The updated state with the generated images paths added.
    """
    if not state['image_prompts']:
        raise ValueError("No image prompts generated yet.")

    # convert AppScriptImagesPrompts to AppSrcScriptImagePrompts
    prompts = state['image_prompts'].to_script_image_prompts(indices=state['image_prompt_indices'])

    # temp local folder for images
    temp_folderpath = os.path.join(state['output_dir'], settings.app.IMAGES_TEMP_FOLDER)
    if not os.path.exists(temp_folderpath):
        os.makedirs(temp_folderpath)

    image_generator.generate_images(
        prompts,
        temp_folderpath
    )

    for i in range(len(state['image_prompts'].image_prompts)):
        folderpath = os.path.join(
            state['output_dir'],
            settings.app.IMAGES_FOLDER_TEMPLATE.format(script_segment=i)
        )
        if not os.path.exists(folderpath):
            os.makedirs(folderpath)

        # the generated images are named 0.png, 1.png, ...
        n_image = len(os.listdir(folderpath))

        # move the generated images to the correct folder
        try:
            filepath = os.path.join(folderpath, f"{n_image}.png")
            os.rename(
                os.path.join(temp_folderpath, f"{i}.png"),
                filepath
                )

            # add the generated image path to the AppScriptImagesPrompts
            state['image_prompts'].image_prompts[i].image_prompts[state['image_prompt_indices'][i]].images_path.append(filepath)
        except FileNotFoundError:
            logger.info(f"No images found at {folderpath}")

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state

def generate_single_image(state: dict, index: str) -> dict:
    """Generate a single image for the given index.

    Args:
        state (dict): The current state of the application.
        index (str): The index of the image prompt to generate an image for.

    Returns:
        dict: The updated state with the generated image path added.
    """
    if not state['image_prompts']:
        raise ValueError("No image prompts generated yet.")

    # convert AppScriptImagesPrompts to AppSrcScriptImagePrompts (with only one prompt)
    prompt = AppScriptImagesPrompts(image_prompts=[state['image_prompts'].image_prompts[index]]).to_script_image_prompts(
        indices=[state['image_prompt_indices'][index]]
    )

    # temp local folder for images
    temp_folderpath = os.path.join(state['output_dir'], settings.app.IMAGES_TEMP_FOLDER)
    if not os.path.exists(temp_folderpath):
        os.makedirs(temp_folderpath)

    image_generator.generate_images(
        prompt,
        temp_folderpath
    )

    folderpath = os.path.join(
        state['output_dir'],
        settings.app.IMAGES_FOLDER_TEMPLATE.format(script_segment=index)
    )

    if not os.path.exists(folderpath):
        os.makedirs(folderpath)

    # the generated images are named 0.png, 1.png, ...
    n_image = len(os.listdir(folderpath))

    # move the generated image to the correct folder
    try:
        filepath = os.path.join(folderpath, f"{n_image}.png")
        os.rename(
            os.path.join(temp_folderpath, f"{0}.png"),
            filepath
        )

        # add the generated image path to the AppScriptImagesPrompts
        state['image_prompts'].image_prompts[index].image_prompts[state['image_prompt_indices'][index]].images_path.append(filepath)

    except FileNotFoundError:
        logger.info(f"No images found at {folderpath}")

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state

def update_prompts_index(state: dict, index: int, value: str) -> dict:
    """Update the index of the selected image prompt.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the image prompt to update.
        value (str): The new index value as a string.

    Returns:
        dict: The updated state.
    """
    state['image_prompt_indices'][index] = value
    return state

def modify_prompt(state: dict, index: int, comment: str) -> tuple[dict, str]:
    """Modify the prompt of the selected image prompt.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the image prompt to modify.
        comment (str): The comment on what to change in the prompt.

    Returns:
        dict: The updated state with the modified prompt added.
    """
    prompts = AppScriptImagesPrompts(image_prompts=[state['image_prompts'].image_prompts[index]]).to_script_image_prompts(
        indices=[state['image_prompt_indices'][index]]
    )

    chosen_storyboard = state['list_storyboards'].storyboards[state['list_storyboards'].selected_storyboard_index]
    lookbook = state['list_storyboards'].lookbook

    new_prompt = storyboard_generator.modify_image_prompt(
        storyboard=chosen_storyboard,
        lookbook=lookbook,
        prompts=prompts,
        index=0,
        comment=comment
    )

    state['image_prompts'].image_prompts[index].image_prompts.append(
        AppImagePrompt(
            prompt=new_prompt.prompt,
            negative_prompt=new_prompt.negative_prompt,
        )
    )

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state, comment

def update_images_index(state: dict, index: int, evt: gr.SelectData) -> dict:
    """Update the index of the selected image for the given prompt index.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the image prompt.
        evt (gr.SelectData): The event data from the image selection.

    Returns:
        dict: The updated state with the selected image path updated.
    """
    selected_image = evt.index
    image_prompt = state['image_prompts'].image_prompts[index]
    filepaths = [filepath for k in range(len(image_prompt.image_prompts))
                 for filepath in image_prompt.image_prompts[k].images_path]
    state['image_prompts'].image_prompts[index].selected_image_path = filepaths[selected_image]

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state

def add_segment(state: dict, index: int) -> dict:
    """Add a text segment after this index.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the segment.

    Returns:
        dict: The updated state with the added text segment.
    """
    state['image_prompts'].image_prompts.insert(
        index+1,
        AppImagesPrompts(
            script_segment='',
            image_prompts=[AppImagePrompt(
                prompt='',
                images_path=[]
            )],
        )
    )

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state

def delete_segment(state: dict, index: int) -> dict:
    """Delete the text segment for at this index.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the segment.

    Returns:
        dict: The updated state with the text segment removed.
    """
    state['image_prompts'].image_prompts.pop(index)

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state

def save_segment(state: dict, index: int, text: str) -> dict:
    """Save the modified text segment at this index.

    Args:
        state (dict): The current state of the application.
        index (int): The index of the segment.
        text (str): The new value of the segment.

    Returns:
        dict: The updated state with the text segment saved.
    """
    state['image_prompts'].image_prompts[index].script_segment = text

    # save the AppScriptImagesPrompts to file
    save_state(state)

    return state

def save_chosen_images(state: dict) -> None:
        """Save the list of images selected by the user.
        Args:
            state (dict): The current state of the application.
        """
        chosen_images_folder = os.path.join(state['output_dir'], settings.app.IMAGES_FINAL_FOLDER)
        if not os.path.exists(chosen_images_folder):
            os.makedirs(chosen_images_folder)

        for i, image_prompt in tqdm(iterable=enumerate(state['image_prompts'].image_prompts), desc="Saving chosen images"):
            filepath = image_prompt.selected_image_path
            if filepath and os.path.exists(filepath):
                dest_path = os.path.join(chosen_images_folder, f"{i}.png")
                with open(filepath, "rb") as src_file, open(dest_path, "wb") as dst_file:
                    dst_file.write(src_file.read())
