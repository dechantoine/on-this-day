from enum import Enum
from typing import Any, List, Union, Optional, Callable

from google.genai import Client, errors, types

from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings

models_pricing = {
    'gemini-2.0-flash':
        {
            'length_limit': 10 ** 9,
            'text_input_short_cost': 0.15 * 10 ** -6,
            'text_input_long_cost': 0.15 * 10 ** -6,
            'text_output_short_cost': 0.6 * 10 ** -6,
            'text_output_long_cost': 0.6 * 10 ** -6,
        },
    'gemini-2.5-flash':
        {
            'length_limit': 200000,
            'text_input_short_cost': 0.30 * 10 ** -6,
            'text_input_long_cost': 0.30 * 10 ** -6,
            'text_output_short_cost': 2.5 * 10 ** -6,
            'text_output_long_cost': 2.5 * 10 ** -6,
        },
    'gemini-2.5-flash-preview-09-2025':
        {
            'length_limit': 200000,
            'text_input_short_cost': 0.30 * 10 ** -6,
            'text_input_long_cost': 0.30 * 10 ** -6,
            'text_output_short_cost': 2.5 * 10 ** -6,
            'text_output_long_cost': 2.5 * 10 ** -6,
        },
    'gemini-2.5-pro':
        {
            'length_limit': 200000,
            'text_input_short_cost': 1.25 * 10 ** -6,
            'text_input_long_cost': 2.5 * 10 ** -6,
            'text_output_short_cost': 10 * 10 ** -6,
            'text_output_long_cost': 15 * 10 ** -6,
        },
}


class LLMGemini:
    """Instantiates a LLM model for Gemini."""

    project: str = Field(default=None)
    model_name: str = Field(default=None)
    location: str = Field(default=None)
    client: Optional[Client] = None

    short_input_text_tokens: int = 0
    long_input_text_tokens: int = 0
    short_output_text_tokens: int = 0
    long_output_text_tokens: int = 0
    short_reasoning_tokens: int = 0
    long_reasoning_tokens: int = 0
    short_tool_use_tokens: int = 0
    long_tool_use_tokens: int = 0
    successful_requests: int = 0
    grounding_requests: int = 0
    total_cost: float = 0

    def __init__(self, model_name: str, **kwargs) -> None:
        """Initializes the VertexAI chat LLM class.

        Args:
            model_name: Name of the Gemini model to use.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(**kwargs)

        self.project = settings.gemini.PROJECT_ID
        self.location = settings.gemini.LOCATION_ID

        self.model_name = model_name

        self.client = Client(vertexai=True, project=self.project, location=self.location)

        try:
            self.client.models.get(model=self.model_name)
        except errors.ClientError:
            logger.error(f"Model {self.model_name} not found in project {self.project} at location {self.location}")
            raise

        logger.info(
            f"LLMGemini initialized with model {self.model_name}"
            f" in project {self.project} at location {self.location}"
        )

    @classmethod
    def update_costs(
        cls,
        model_name: str,
        response: types.GenerateContentResponse,
    ) -> None:
        """Update costs based on the response.

        Args:
            model_name: Name of the model.
            response: Response from the Gemini API.
        """
        usage_metadata = response.usage_metadata

        prompt_tokens = usage_metadata.prompt_token_count if usage_metadata.prompt_token_count else 0
        completion_tokens = usage_metadata.candidates_token_count if usage_metadata.candidates_token_count else 0
        reasoning_tokens = usage_metadata.thoughts_token_count if usage_metadata.thoughts_token_count else 0
        tool_use_tokens = (
            usage_metadata.tool_use_prompt_token_count if usage_metadata.tool_use_prompt_token_count else 0
        )

        cls.short_input_text_tokens += min(prompt_tokens, models_pricing[model_name]["length_limit"])
        cls.long_input_text_tokens += max(0, prompt_tokens - models_pricing[model_name]["length_limit"])
        cls.short_output_text_tokens += min(completion_tokens, models_pricing[model_name]["length_limit"])
        cls.long_output_text_tokens += max(0, completion_tokens - models_pricing[model_name]["length_limit"])
        cls.short_reasoning_tokens += min(reasoning_tokens, models_pricing[model_name]["length_limit"])
        cls.long_reasoning_tokens += max(0, reasoning_tokens - models_pricing[model_name]["length_limit"])
        cls.short_tool_use_tokens += min(tool_use_tokens, models_pricing[model_name]["length_limit"])
        cls.long_tool_use_tokens += max(0, tool_use_tokens - models_pricing[model_name]["length_limit"])
        cls.successful_requests += 1
        cls.grounding_requests += 1 if response.candidates[0].grounding_metadata else 0

        cls.total_cost = (
            cls.short_input_text_tokens * models_pricing[model_name]["text_input_short_cost"]
            + cls.long_input_text_tokens * models_pricing[model_name]["text_input_long_cost"]
            + cls.short_output_text_tokens * models_pricing[model_name]["text_output_short_cost"]
            + cls.long_output_text_tokens * models_pricing[model_name]["text_output_long_cost"]
            + cls.short_reasoning_tokens * models_pricing[model_name]["text_output_short_cost"]
            + cls.long_reasoning_tokens * models_pricing[model_name]["text_output_long_cost"]
            + cls.short_tool_use_tokens * models_pricing[model_name]["text_output_short_cost"]
            + cls.long_tool_use_tokens * models_pricing[model_name]["text_output_long_cost"]
        )

    @classmethod
    def print_costs(cls) -> None:
        """Prints total costs of this class in the current runtime."""
        logger.info(
            f"Total cost so far: "
            f"\n{cls.total_cost:.9f} USD, "
            f"\n{cls.successful_requests} requests, "
            f"\n{cls.short_input_text_tokens} short input text tokens count,"
            f"\n{cls.long_input_text_tokens} long input text tokens count,"
            f"\n{cls.short_output_text_tokens} short output text tokens count,"
            f"\n{cls.long_output_text_tokens} long output text tokens count."
            f"\n{cls.short_reasoning_tokens} short reasoning tokens count,"
            f"\n{cls.long_reasoning_tokens} long reasoning tokens count.",
            f"\n{cls.short_tool_use_tokens} short tool use tokens count,"
            f"\n{cls.long_tool_use_tokens} long tool use tokens count.",
        )

    def generate(
        self,
        list_contents: Union[types.ContentListUnion, types.ContentListUnionDict],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        """Generates text based on the input prompts.

        Args:
            list_contents: A list of contents.
            config: A GenerateContentConfig object.

        Returns:
            A GenerateContentResponse object.

        """
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=list_contents,
            config=config,
        )

        LLMGemini.update_costs(
            model_name=self.model_name,
            response=response,
        )

        return response

    def generate_from_prompt(
        self,
        prompt: str,
        temperature: float = 0.,
    ) -> str:
        """Generates text based on the input prompts.

        Args:
            prompt: A prompt.
            temperature: A temperature parameter.

        Returns:
            A GenerateContentResponse object.

        """
        list_contents = [types.UserContent(parts=[types.Part.from_text(text=prompt)])]

        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="text/plain",
        )

        response = self.generate(
            list_contents=list_contents,
            config=generation_config,
        )

        return response.candidates[0].content.parts[0].text

    def generate_function_call(
        self,
        system_prompt: str,
        list_contents: Union[types.ContentListUnion, types.ContentListUnionDict],
        tools: Optional[list[Callable]],
    ) -> types.FunctionCall:
        """Generates a function call. The model is forced to choose a function in tools.

        Args:
            system_prompt: The system_prompt to use.
            list_contents: A list of contents.
            tools: A list of callables.

        Returns:
            A FunctionCall object.
        """
        generation_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True,
            ),
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.ANY,
                ),
            ),
        )

        function_call = self.generate(
            list_contents=list_contents,
            config=generation_config,
        ).function_calls[0]

        return function_call

    def generate_with_enum(
        self,
        enums: List[Any],
        multiple: bool,
        prompt: str,
        temperature: float = 0.0,
        tools: Optional[list[Callable]] = None,
    ) -> Union[Any, List[Any]]:
        """Generate text with enum output.

        Args:
            enums: The list of enums to use.
            multiple: Whether to allow Gemini to choose multiple enums.
            prompt: The prompt to use.
            temperature: The temperature to use.
            tools: A list of callables.

        Returns:
            The chosen enum or list of chosen enums.
        """
        choices = {f"choice_{i}": choice for i, choice in enumerate(enums)}
        choices_enum = Enum("ChoicesEnum", choices)

        class Choice(BaseModel):
            choice: choices_enum = Field(..., title="Chosen Enum")

        class Choices(BaseModel):
            choices: List[choices_enum] = Field(..., title="List of Chosen Enums")

        output_type = Choices if multiple else Choice

        response = self.generate_with_structured_output(
            output_type=output_type,
            prompt=prompt,
            temperature=temperature,
            tools=tools,
        )

        if multiple:
            return [choice.value for choice in response.choices]
        else:
            return response.choice.value

    def generate_with_structured_output(
            self,
            output_type: BaseModel,
            prompt: str,
            temperature: float = 0.0,
            tools: Optional[list[Callable]] = None,
    ) -> BaseModel:
        """Generates text based on the input prompts.

        Args:
            output_type: A Pydantic class.
            prompt: A string prompt.
            temperature: A float temperature.
            tools: A list of callables.

        Returns:
            A Pydantic class object.
        """
        list_contents = [types.UserContent(parts=[types.Part.from_text(text=prompt)])]

        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=output_type,
            tools=tools,
        )

        response = self.generate(
            list_contents=list_contents,
            config=generation_config,
        )

        parsed = response.parsed

        return parsed

    def generate_with_grounding(
        self,
        prompt: str,
        temperature: float = 0.0,
    ) -> types.GenerateContentResponse:
        """Generates text based on the input prompts.

        Args:
            prompt: A string prompt.
            temperature: A float temperature.
        Returns:
            A GenerateContentResponse object.
        """
        list_contents = [types.UserContent(parts=[types.Part.from_text(text=prompt)])]

        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="text/plain",
            tools=[
                types.Tool(
                    google_search=types.GoogleSearch(
                    ),
                ),
            ],
        )

        response = self.generate(
            list_contents=list_contents,
            config=generation_config,
        )

        return response