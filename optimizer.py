import os
import json
from typing import Tuple
from pydantic import BaseModel, Field

class CreativePackage(BaseModel):
    higgsfield_prompt: str = Field(
        description="Prompt conciso en inglés para transformar o animar el video en Higgsfield AI"
    )
    youtube_title: str = Field(
        description="Título viral en español de máximo 70 caracteres que termine con #Shorts"
    )
    tiktok_caption: str = Field(
        description="Descripción corta en español con gancho y 4 hashtags virales"
    )

class TokenOptimizerAgent:
    """
    Agente cognitivo ultra-eficiente.
    Consolidado en 1 sola llamada estructurada (~200-300 tokens totales por clip).
    Soporta: Gemini (ultra barato), OpenAI (gpt-4o-mini) o Ollama (local, $0 USD).
    """
    def __init__(self, provider: str = "gemini", model_name: str = "gemini-3.5-flash-lite", base_style: str = ""):
        self.provider = provider.lower()
        self.model_name = model_name
        self.base_style = base_style

        if self.provider == "gemini":
            from google import genai
            self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        elif self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.provider == "ollama":
            from openai import OpenAI
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"
            )
        else:
            raise ValueError(f"Proveedor LLM no soportado: {provider}")

    def generate_package(
        self,
        streamer_name: str,
        clip_title: str,
        transcript: str
    ) -> Tuple[CreativePackage, int, int]:
        """
        Genera el prompt de Higgsfield + metadatos de redes en una sola llamada.
        Retorna: (CreativePackage, prompt_tokens, completion_tokens)
        """
        system_msg = (
            "Eres un productor de videos virales cortos. "
            "Responde ÚNICAMENTE con el JSON solicitado, sin explicaciones extra. "
            "El prompt de Higgsfield DEBE incluir explícitamente subtítulos dinámicos en español "
            f"y el siguiente estilo visual obligatorio: {self.base_style}."
        )
        user_msg = (
            f"Streamer: {streamer_name}\n"
            f"Título del clip: {clip_title}\n"
            f"Transcripción: {transcript or 'Sin audio transcrito'}"
        )

        prompt_tokens = 0
        completion_tokens = 0

        if self.provider == "gemini":
            from google.genai import types
            fallback_models = []
            for m in [self.model_name, "gemini-3.5-flash-lite", "gemini-3.8-flash"]:
                if m not in fallback_models:
                    fallback_models.append(m)

            last_error = None
            for candidate_model in fallback_models:
                try:
                    response = self.client.models.generate_content(
                        model=candidate_model,
                        contents=f"{system_msg}\n\n{user_msg}",
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=CreativePackage,
                            temperature=0.7
                        )
                    )
                    data = json.loads(response.text)
                    package = CreativePackage(**data)

                    if response.usage_metadata:
                        prompt_tokens = response.usage_metadata.prompt_token_count or 0
                        completion_tokens = response.usage_metadata.candidates_token_count or 0

                    if candidate_model != self.model_name:
                        print(f"[Optimizer] '{self.model_name}' saturado; se usó '{candidate_model}' automáticamente.")
                    return package, prompt_tokens, completion_tokens
                except Exception as e:
                    last_error = e
                    print(f"[Optimizer] Modelo '{candidate_model}' no disponible temporalmente ({type(e).__name__}). Probando alternativa...")

            # Respaldo determinista (0 tokens) si todos los endpoints de Gemini están saturados
            print(f"[Optimizer] Usando plantilla local de respaldo (0 tokens). Último error: {last_error}")
            fallback_pkg = CreativePackage(
                higgsfield_prompt=f"{self.base_style}. Scene inspired by Twitch streamer {streamer_name}: {clip_title}.",
                youtube_title=f"{streamer_name}: {clip_title[:45]} 🔥 #Shorts",
                tiktok_caption=f"Momentazo de {streamer_name}: {clip_title[:60]} 🤯 #twitch #clips #{streamer_name} #viral"
            )
            return fallback_pkg, 0, 0

        else:
            # OpenAI o Ollama local
            response = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                response_format=CreativePackage,
                temperature=0.7
            )
            package = response.choices[0].message.parsed
            if response.usage:
                prompt_tokens = response.usage.prompt_tokens or 0
                completion_tokens = response.usage.completion_tokens or 0

            return package, prompt_tokens, completion_tokens
