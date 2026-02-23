from dotenv import load_dotenv, find_dotenv
import os
import json
from google import genai
from google.genai import types as genai_types

load_dotenv(find_dotenv())
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")


class CallGemma:
    def __init__(self, api_key=GOOGLE_API_KEY, model=GOOGLE_MODEL):
        self.api_key = api_key
        self.model = model
        self._client = genai.Client(api_key=self.api_key)

    def response_to_json(self, response_text: str) -> dict:
        """
        Converts the response text to a JSON dictionary.
        Handles potential markdown formatting and parsing errors.
        input: response_text (str): The raw response text from the model.
        output: dict: Parsed JSON dictionary or empty dict on failure.
        """
        try:
            cleaned_text = response_text.strip()
            if "```json" in cleaned_text.lower():
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].strip()
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return {}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {}

    def get_gemma_response(
        self,
        sys_prompt: str,
        news_article: str,
        temperature: float = 0.05,
        api_key: str = None,
        model: str = None,
    ) -> dict:
        """
        Calls the Gemini model using the google-genai SDK.
        Returns the parsed JSON response.
        input: sys_prompt (str): The system prompt for the model.
               news_article (str): The news article to analyze.
               temperature (float): The temperature setting for generation.
               api_key (str): Optional override API key.
               model (str): Optional override model name.
        output: dict: Parsed JSON response from the model.
        """
        try:
            client = genai.Client(api_key=api_key or self.api_key)
            model_name = model or self.model

            response = client.models.generate_content(
                model=model_name,
                contents=f"{sys_prompt}\nNews Article: {news_article}",
                config=genai_types.GenerateContentConfig(temperature=temperature),
            )

            if response.text:
                return self.response_to_json(response.text)
            else:
                print("Empty response received")
                return {}

        except Exception as e:
            print(f"Error generating response: {e}")
            return {}

    def load_prompt(self, prompt_name: vars) -> dict:
        """
        Loads prompts from a YAML file.
        input: filepath (str): Path to the YAML file containing prompts.
        output: dict: Dictionary of prompts.
        """
        try:
            from . import prompts

            return prompts[prompt_name]
        except ImportError as e:
            print(f"Error importing prompt: {e}")
            return ""
