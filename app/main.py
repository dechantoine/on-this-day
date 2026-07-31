from datetime import datetime

import gradio as gr

from app.events_tab import (
    get_events,
    select_and_save_event
)
from app.scripts_tab import (
    generate_candidate_hooks,
    script_generator,
    generate_candidate_script,
    display_script,
    select_script
)
from app.storyboard_tab import (
    generate_storyboards,
    select_storyboard,
    storyboard_to_markdown
)
from app.images_tab import (
    storyboard_generator,
    image_generator,
    generate_image_prompts,
    generate_all_images,
    generate_single_image,
    update_prompts_index,
    modify_prompt,
    update_images_index,
    add_segment,
    delete_segment,
    save_segment,
    save_chosen_images
)
from app.animation_tab import (
    generate_animations,
)
from app.utils import display_event, display_qualified_event, init_state, load_state

with gr.Blocks(title="On This Day") as app:
    # Shared state across tabs
    state = gr.State(init_state())

    with gr.Row():
        year_input = gr.Number(value=datetime.now().year, label="Year", precision=0)
        month_input = gr.Number(value=datetime.now().month, label="Month", minimum=1, maximum=12, precision=0)
        day_input = gr.Number(value=datetime.now().day, label="Day", minimum=1, maximum=31, precision=0)

        # reload state for all tabs when date changes
        year_input.change(
            load_state,
            inputs=[year_input, month_input, day_input],
            outputs=[state]
        )

        month_input.change(
            load_state,
            inputs=[year_input, month_input, day_input],
            outputs=[state]
        )

        day_input.change(
            load_state,
            inputs=[year_input, month_input, day_input],
            outputs=[state]
        )

    with gr.Tabs():
        with gr.Tab("Events"):
            with gr.Column():
                @gr.render(inputs=state)
                def render_events_tab(state_dict):
                    if state_dict['qualified_events']:
                        len_qualified_events = len(state_dict["qualified_events"].qualified_events)
                    else:
                        len_qualified_events = 0
                    with gr.Row():
                        get_events_btn = gr.Button("Get Events for This Date")

                    event_slider = gr.Slider(
                        minimum=0,
                        maximum=max(len_qualified_events-1, 1),
                        step=1,
                        value=0,
                        label="Event Index",
                        visible=len_qualified_events > 0
                    )

                    with gr.Row():
                        event_display = gr.Markdown(
                            value=(display_event(state_dict['qualified_events'].qualified_events[0]) if len_qualified_events >0
                                   else "Select a date and fetch events to begin"),
                            visible=len_qualified_events > 0
                        )
                        event_qualify_display = gr.Markdown(
                            value=(display_qualified_event(state_dict['qualified_events'].qualified_events[0]) if len_qualified_events > 0
                                   else "No events qualified yet."),
                            visible=len_qualified_events > 0
                        )

                    select_event_btn = gr.Button("Select This Event")

                    # actions
                    get_events_btn.click(
                        get_events,
                        inputs=state,
                        outputs=state
                    ).success(
                        lambda state: gr.Slider(
                            visible=True,
                            maximum=len(state['events'].events) - 1,
                            value=0,
                        ),
                        inputs=state,
                        outputs=event_slider
                    )

                    event_slider.change(
                        lambda state, index: gr.Markdown(
                            value=display_event(state['qualified_events'].qualified_events[index]),
                            visible=True),
                        inputs=[state, event_slider],
                        outputs=event_display,
                    ).then(
                        lambda state, index: gr.Markdown(
                            value=(display_qualified_event(state['qualified_events'].qualified_events[index])
                                   if state['qualified_events']
                                   else "No events qualified yet."),
                            visible=True
                        ),
                        inputs=[state, event_slider],
                        outputs=event_qualify_display
                    )

                    select_event_btn.click(
                        lambda state, index: select_and_save_event(state, index),
                        inputs=[state, event_slider],
                        outputs=state
                    )


        with gr.Tab("Scripts"):
            with gr.Column():
                with gr.Row():
                    @gr.render(inputs=state)
                    def render_script_tab(state_dict):
                        if state_dict['chosen_event']:
                            gr.Markdown(
                                value=display_qualified_event(state_dict['chosen_event']),
                            )
                        else:
                            gr.Markdown(
                                value="No event for this date. Please choose an event first.",
                            )

                        with gr.Column():
                            if state_dict['list_scripts']:
                                len_hooks = len([hook.hook for hook in state_dict['list_scripts'].hooks])
                            else:
                                len_hooks = 0

                            hook_temp_slider = gr.Slider(
                                minimum=0,
                                maximum=2,
                                step=0.1,
                                value=0.7,
                                label="Hooks temperature",
                                visible=state_dict['chosen_event'] is not None,
                            )

                            n_hooks_slider = gr.Slider(
                                minimum=1,
                                maximum=5,
                                step=1,
                                value=3,
                                label="Number of hooks per generation",
                                visible=state_dict['chosen_event'] is not None,
                            )

                            generate_hooks_btn = gr.Button(
                                value="Generate hooks",
                                visible=state_dict['chosen_event'] is not None,
                            )

                            hooks_slider = gr.Slider(
                                minimum=0,
                                maximum=max(len_hooks - 1, 1),
                                step=1,
                                value=0,
                                label="Hook index",
                                visible=len_hooks > 1
                            )
                            hook_display = gr.Markdown(
                                value=(f"*{state_dict['list_scripts'].hooks[0].hook}*" if len_hooks > 0
                                       else "No hooks generated yet."),
                                visible=len_hooks > 0
                            )
                            script_temp_slider = gr.Slider(
                                minimum=0,
                                maximum=2,
                                step=0.1,
                                value=0.7,
                                label="Scripts temperature",
                                interactive=True,
                                visible=len_hooks > 0
                            )
                            generate_script_btn = gr.Button(
                                value="Generate script from this hook",
                                visible=len_hooks > 0
                            )

                        with gr.Column():
                            if state_dict['list_scripts']:
                                len_scripts = sum(
                                    [len(hook.scripts) if hook.scripts else 0
                                     for hook in state_dict['list_scripts'].hooks])
                            else:
                                len_scripts = 0

                            scripts_slider = gr.Slider(
                                minimum=0,
                                maximum=max(len_scripts - 1, 1),
                                step=1,
                                value=0,
                                label="Generated script index",
                                visible=len_scripts > 1
                            )
                            script_display = gr.Markdown(
                                value=(display_script(state_dict, 0) if len_scripts > 0
                                       else "No scripts generated yet."),
                                visible=len_scripts > 0
                            )

                            save_script_btn = gr.Button(
                                "Select & save this script",
                                visible=len_scripts > 0
                            )

                        # actions for elements in render
                        hook_temp_slider.change(
                            lambda temp: setattr(script_generator, 'hook_temperature', temp),
                            inputs=hook_temp_slider,
                        )

                        generate_hooks_btn.click(
                            generate_candidate_hooks,
                            inputs=[state, n_hooks_slider],
                            outputs=state
                        ).success(
                            lambda state: gr.Slider(
                                visible=True,
                                maximum=len([hook.hook for hook in state_dict['list_scripts'].hooks]) - 1,
                                value=len([hook.hook for hook in state_dict['list_scripts'].hooks]) - 1,
                            ),
                            inputs=state,
                            outputs=hooks_slider
                        )

                        hooks_slider.change(
                            lambda state, hook_index: f"*{state['list_scripts'].hooks[hook_index].hook}*",
                            inputs=[state, hooks_slider],
                            outputs=hook_display,
                        )

                        script_temp_slider.change(
                            lambda temp: setattr(script_generator, 'script_temperature', temp),
                            inputs=script_temp_slider,
                        )

                        generate_script_btn.click(
                            generate_candidate_script,
                            inputs=[state, hooks_slider],
                            outputs=state
                        ).success(
                            lambda state: gr.Slider(
                                visible=True,
                                maximum=sum([len(hook.scripts) if hook.scripts else 0
                                             for hook in state['list_scripts'].hooks]) - 1,
                                value=sum([len(hook.scripts) if hook.scripts else 0
                                           for hook in state['list_scripts'].hooks]) - 1,
                            ),
                            inputs=state,
                            outputs=scripts_slider
                        )

                        scripts_slider.change(
                            display_script,
                            inputs=[state, scripts_slider],
                            outputs=script_display,
                        )

                        save_script_btn.click(
                            select_script,
                            inputs=[state, scripts_slider],
                            outputs=state
                        )

        with gr.Tab("Storyboards"):
            with gr.Column():
                @gr.render(inputs=state)
                def render_storyboards_tab(state_dict):
                    if state_dict['list_storyboards']:
                        len_storyboards = len(state_dict['list_storyboards'].storyboards)
                    else:
                        len_storyboards = 0

                    generate_storyboards_btn = gr.Button("Generate Storyboards from Chosen Script")

                    storyboard_temp_slider = gr.Slider(
                        minimum=0,
                        maximum=2,
                        step=0.1,
                        value=0.2,
                        label="Storyboard temperature",
                    )

                    storyboards_slider = gr.Slider(
                        minimum=0,
                        maximum=max(len_storyboards-1, 1),
                        step=1,
                        value=0,
                        label="Storyboard Index",
                        visible=len_storyboards > 0
                    )

                    storyboard_display = gr.Markdown(
                        value=(
                            storyboard_to_markdown(state_dict['list_storyboards'].storyboards[0])
                            if len_storyboards > 0
                            else "No storyboards generated yet."
                        ),
                        visible=len_storyboards > 0
                    )

                    select_storyboard_btn = gr.Button(
                        value="Select This Storyboard",
                        visible=len_storyboards > 0
                    )

                    # actions
                    storyboard_temp_slider.change(
                        lambda temp: setattr(storyboard_generator, 'temperature', temp),
                        inputs=storyboard_temp_slider,
                    )

                    generate_storyboards_btn.click(
                        generate_storyboards,
                        inputs=state,
                        outputs=state
                    ).success(
                        lambda state: gr.Slider(
                            visible=True,
                            maximum=len(state['list_storyboards'].storyboards) - 1,
                            value=0,
                        ),
                        inputs=state,
                        outputs=storyboards_slider
                    )

                    storyboards_slider.change(
                        lambda state, index: gr.Markdown(
                            value=storyboard_to_markdown(state['list_storyboards'].storyboards[index]),
                            visible=True),
                        inputs=[state, storyboards_slider],
                        outputs=storyboard_display,
                    )

                    select_storyboard_btn.click(
                        select_storyboard,
                        inputs=[state, storyboards_slider],
                        outputs=state
                    )

        with gr.Tab("Images"):
            with gr.Column():
                @gr.render(inputs=state)
                def render_image_tab(state_dict):
                    with gr.Row():
                        with gr.Sidebar():
                            prompt_temp_slider = gr.Slider(
                                minimum=0,
                                maximum=2,
                                step=0.1,
                                value=0.2,
                                label="Prompt temperature",
                            )
                            image_guidance_scale_slider = gr.Slider(
                                minimum=0,
                                maximum=10,
                                step=0.1,
                                value=1,
                                label="Image guidance scale"
                            )

                            if state_dict['enhanced_script']:
                                gr.Markdown(str(state_dict['enhanced_script']))
                            elif state_dict['chosen_script']:
                                gr.Markdown(str(state_dict['chosen_script']))
                            else:
                                gr.Markdown("No script for this date, please generate a script first.")

                        with gr.Column():
                            with gr.Row():
                                generate_prompts_images_btn = gr.Button("Generate prompts and images for all segments")
                                generate_images_btn = gr.Button("Generate images for all prompts")

                    segments = []
                    segments_add = []
                    segments_delete = []
                    segments_save = []
                    prompts = []
                    prompt_sliders = []
                    galleries = []
                    prompt_buttons = []
                    textboxes = []
                    image_buttons = []
                    if 'image_prompts' in state_dict and state_dict['image_prompts']:
                        for i, image_prompt in enumerate(state_dict['image_prompts'].image_prompts):
                            with gr.Row():
                                with gr.Column():
                                    segments.append(
                                        gr.Textbox(
                                            label=f"Segment {i}",
                                            value=image_prompt.script_segment,
                                            interactive=True
                                        )
                                    )
                                    with gr.Row():
                                        segments_add.append(
                                            gr.Button("Add a segment below")
                                        )
                                        segments_delete.append(
                                            gr.Button("Delete this segment")
                                        )
                                        segments_save.append(
                                            gr.Button("Save this segment")
                                        )

                                with gr.Column():
                                    prompts.append(
                                        gr.Markdown(
                                            f"**Prompt:** {image_prompt.image_prompts[state_dict['image_prompt_indices'][i]].prompt}"
                                        )
                                    )
                                    prompt_sliders.append(
                                        gr.Slider(
                                            visible=True if len(image_prompt.image_prompts) > 1 else False,
                                            minimum=0,
                                            maximum=max(len(image_prompt.image_prompts)-1,1),
                                            step=1,
                                            value=state_dict['image_prompt_indices'][i])
                                    )

                                filepaths = [filepath for k in range(len(image_prompt.image_prompts))
                                             for filepath in image_prompt.image_prompts[k].images_path]
                                selected_index = (filepaths.index(image_prompt.selected_image_path)
                                                  if image_prompt.selected_image_path
                                                  else None)
                                galleries.append(gr.Gallery(value=filepaths,
                                                            selected_index=selected_index,
                                                            type="filepath",
                                                            interactive=False))

                                with gr.Column():
                                    prompt_buttons.append(gr.Button("Regenerate Prompt"))
                                    textboxes.append(gr.Textbox(value="", label="What's wrong with this image?"))
                                    image_buttons.append(gr.Button("Regenerate Image"))

                        build_button = gr.Button("Save the chosen images for animation",
                                  interactive=all([image_prompt.selected_image_path for image_prompt in state_dict['image_prompts'].image_prompts]))

                    else:
                        gr.Markdown("No image prompts generated yet.")

                    # actions for elements in render
                    prompt_temp_slider.change(
                        lambda temp: setattr(storyboard_generator, 'temperature', temp),
                        inputs=prompt_temp_slider,
                    )

                    image_guidance_scale_slider.change(
                        lambda scale: setattr(image_generator, 'guidance_scale', scale),
                        inputs=image_guidance_scale_slider,
                    )

                    generate_prompts_images_btn.click(
                        generate_image_prompts,
                        inputs=state,
                        outputs=state
                    ).success(
                        generate_all_images,
                        inputs=state,
                        outputs=state
                    )

                    generate_images_btn.click(
                        generate_all_images,
                        inputs=state,
                        outputs=state
                    )

                    for i in range(len(image_buttons)):
                        image_buttons[i].click(
                            generate_single_image,
                            inputs=[state, gr.State(i)],
                            outputs=state
                        ).success(
                            lambda state, i: gr.Gallery(
                                value=[filepath for k in range(len(state_dict['image_prompts'].image_prompts[i].image_prompts))
                                       for filepath in state_dict['image_prompts'].image_prompts[i].image_prompts[k].images_path]),
                            inputs=[state, gr.State(i)],
                            outputs=galleries[i]
                        )

                        segments_add[i].click(
                            add_segment,
                            inputs=[state, gr.State(i)],
                            outputs=state
                        )

                        segments_delete[i].click(
                            delete_segment,
                            inputs=[state, gr.State(i)],
                            outputs=state
                        )

                        segments_save[i].click(
                            save_segment,
                            inputs=[state, gr.State(i), segments[i]],
                            outputs=state
                        )

                        prompt_sliders[i].change(
                            update_prompts_index,
                            inputs=[state, gr.State(i), prompt_sliders[i]],
                            outputs=state
                        )

                        prompt_buttons[i].click(
                            modify_prompt,
                            inputs=[state, gr.State(i), textboxes[i]],
                            outputs=[state, textboxes[i]]
                        ).success(
                            lambda state: gr.Slider(visible=True,
                                                    minimum=0,
                                                    maximum=len(state['image_prompts'].image_prompts[i].image_prompts) - 1,
                                                    step=1,
                                                    value=len(state['image_prompts'].image_prompts[i].image_prompts) - 1
                                                    ),
                            inputs=state,
                            outputs=prompt_sliders[i]
                        )

                        galleries[i].select(
                            update_images_index,
                            inputs=[state, gr.State(i)],
                            outputs=state
                        ).then(
                            lambda state: gr.Button(
                                interactive=all([image_prompt.selected_image_path
                                                 for image_prompt in state_dict['image_prompts'].image_prompts])),
                            inputs=state,
                            outputs=build_button
                        )

                        build_button.click(
                            save_chosen_images,
                            inputs=state,
                        )

        with gr.Tab("Animations"):
            with gr.Column():
                @gr.render(inputs=state)
                def render_image_tab(state_dict):
                    with gr.Row():
                        with gr.Column():
                            generate_animations_btn = gr.Button("Generate animations for all prompts")

                    segments = []
                    prompts = []
                    images = []
                    if 'animation_prompts' in state_dict and state_dict['animation_prompts']:
                        for i, scene in enumerate(state_dict['animation_prompts'].scenes):
                            with gr.Row():
                                with gr.Column():
                                    segments.append(
                                        gr.Textbox(
                                            label=f"Segment {i}",
                                            value=scene.script_segment,
                                            interactive=False
                                        )
                                    )

                                with gr.Column():
                                    prompts.append(
                                        gr.Textbox(
                                            label=f"Prompt {i}",
                                            value=scene.animation_prompt,
                                            show_copy_button=True
                                        )
                                    )

                                image_filepath = state_dict['image_prompts'].get_selected_image_filepath(i)
                                images.append(gr.Image(
                                    value=image_filepath,
                                    height=320,
                                    width=180,
                                    interactive=False
                                ))

                    else:
                        gr.Markdown("No animation prompts generated yet.")

                    # actions for elements in render
                    generate_animations_btn.click(
                        generate_animations,
                        inputs=state,
                        outputs=state
                    )
                ### end of render


if __name__ == "__main__":
    app.launch()