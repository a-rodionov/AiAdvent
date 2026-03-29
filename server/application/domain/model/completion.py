from pydantic import BaseModel, Field


class CompletionConfig(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    max_tokens: int = Field(ge=1)
    system_prompt: str | None = None
    system_prompt_path: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop_sequences: list[str] | None = None
    output_config: type[BaseModel] | None = None
    output_config_path: str | None = None

    def __copy__(self) -> "CompletionConfig":
        new_instance = CompletionConfig(
            provider=self.provider,
            model=self.model,
            max_tokens=self.max_tokens,
            system_prompt=self.system_prompt,
            system_prompt_path=None,
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
            stop_sequences=self.stop_sequences,
            output_config=self.output_config,
            output_config_path=None,
        )
        return new_instance


def format_completion_config(completion_config: CompletionConfig) -> str:
    formated_output = ""
    for name, value in completion_config.model_dump().items():
        if value is not None:
            formated_output += (f"  {name + ':':<21} {value}\n")
    return formated_output
