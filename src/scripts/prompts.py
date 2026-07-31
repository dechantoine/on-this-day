### WIKI PROMPTS ###

extract_events = (
"""<Your mission>
Extract the events that happened from this Wikipedia HTML page. Make sure to include the year, description, and all the href links related to the event.

<HTML page>
{html_page}
"""
)

choose_page = (
"""<Your mission>
You are an historian tasked with writing an extended summary of an historical event.
To do so, you first need to choose which Wikipedia pages should be consulted and provided to you for the next step.
Given the provided short description of the event, select the ones that you think are the most relevant to the task.
Focus on selecting the pages which may contains information you are not aware of.
For example, if the event is about the first moon landing, you may want to select the page about the Apollo 11 mission, but you will leave aside the page about the moon itself and about the NASA.

<Event description>
{description}

<Wikipedia pages>
{pages}
"""
)

short_summary = (
"""<Your mission>
You are an historian working closely with a Youtuber to produce short documentaries on historical events.
Your task is to write an short summary of an historical event based on the description provided and the content of Wikipedia pages related to it.
The summary should be engaging and informative, and should include all the relevant information to grasp the event.
It will be used to determine if the event is suitable for a short documentary.
Please adopt a neutral tone in your summary.

<Event description>
{description}

<Wikipedia pages>
{pages}
"""
)

qualify_event = (
"""<Your mission>
Given the summary of an historical event, you need to identify the criteria that apply to this event.
Please provide the identified criteria and the piece of information that led to the identification of the criteria.

<Event summary>
{summary}
"""
)

### SCRIPT PROMPTS ###
script_hooks = (
"""<Your Mission>
You are a master storyteller, a YouTuber who transforms complex historical events into gripping short documentaries.
Your primary goal is to stop the scroll and immediately captivate your audience within the first three seconds.

Your task is to brainstorm a series of powerful, attention-grabbing **opening sentences** for a video about a specific historical event.
Each sentence will be the *very first thing* the viewer hears, so it must be irresistible, create immediate intrigue, and make them want to know more.
Think less like a textbook and more like a movie trailer.

<Core Principles for a Killer Hook>
- **Intrigue & Mystery:** Start with a question or a statement that makes the viewer ask "What happens next?" or "Why?".
- **Shock & Disbelief:** Present a little-known, counter-intuitive, or shocking fact about the event that challenges what people think they know.
- **Human Connection:** Focus on a personal story, a relatable emotion, or a dramatic decision made by a single person that had massive consequences.
- **Challenge Assumptions:** Directly confront and dismantle a common misconception about the event.
- **High Stakes:** Hint at the massive, unforeseen consequences of a seemingly small action or decision.

<Event Description>
{description}

<Historical Context: Wikipedia Pages>
{pages}
"""
)

script_full = (
"""<Your Mission>
You are a master scriptwriter, collaborating with a historian to create a short, powerful YouTube documentary for the series 'On This Day...'. Your task is to write a full video script that brings a historical event to life.

The script must be a compelling narrative, not a dry report. It should grab the viewer with the pre-selected hook and take them on a journey with a clear beginning, middle, and end. The story must flow logically from the hook, using it as the central theme or question that the video will answer.

<Guiding Principles for the Script>
- **Adapt to your public:** Your public will be international and not highly skilled in English. Stick mainly to simple, universal vocabulary.
- **Narrative First, Facts Second:** Don't just list information from Wikipedia. Weave the key facts into a story. What is the conflict? Who are the main characters? What was at stake?
- **Show, Don't Tell:** Write in a way that helps the viewer visualize the events. Use descriptive language. Instead of saying "he was brave," describe the brave thing he did.
- **Pacing is Everything:** The script should be concise (~250-350 words) and maintain a dynamic pace suitable for a short-form documentary. Use short and impactful sentences to keep the narration engaging.
- **Payoff the Promise:** The entire script must build on the promise of the hook. By the end, the viewer should feel that the initial intriguing statement has been fully explained and resolved.

<Event Date>
{date}

<The Chosen Hook>
This is your starting point. The entire script must be built around this single sentence.
{hook}

<Historical Context: Wikipedia Pages>
Use these sources to build your narrative and ensure historical accuracy.
{pages}
"""
)