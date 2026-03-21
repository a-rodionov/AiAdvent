import sys
import os
import signal
import asyncio
import argparse
from enum import Enum
from config import load_config, ModelConfig
from dotenv import load_dotenv
from anthropic import AsyncAnthropic, APIError, AuthenticationError, transform_schema


class StopReason(str, Enum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    PAUSE_TURN = "pause_turn"
    REFUSAL = "refusal"


STOP_REASON_DESCRIPTIONS = {
    StopReason.END_TURN: "The model reached a natural stopping point.",
    StopReason.MAX_TOKENS: "We exceeded the requested max_tokens or the model's maximum.",
    StopReason.STOP_SEQUENCE: "One of your provided custom stop_sequences was generated.",
    StopReason.TOOL_USE: "The model invoked one or more tools.",
    StopReason.PAUSE_TURN: "We paused a long-running turn. You may provide the response back as-is in a subsequent request to let the model continue.",
    StopReason.REFUSAL: "When streaming classifiers intervene to handle potential policy violations.",
}


async def run(config: ModelConfig, verbose: bool) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)

    if verbose:
        config.print_config()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)

    try:
        messages = []
        while True:
            user_input = input("User: ")
            if not user_input.strip():
                continue

            messages.append({"role": "user", "content": user_input})

            try:
                assistant_text = ""
                print("Model: ", end="", flush=True)
                kwargs = {
                    "max_tokens": config.max_tokens,
                    "messages": messages,
                    "model": config.model,
                }
                if config.system_prompt:
                    kwargs["system"] = config.system_prompt
                if config.temperature is not None:
                    kwargs["temperature"] = config.temperature
                if config.top_k is not None:
                    kwargs["top_k"] = config.top_k
                if config.temperature is None and config.top_p is not None:
                    kwargs["top_p"] = config.top_p
                if config.stop_sequences is not None:
                    kwargs["stop_sequences"] = config.stop_sequences
                if config.output_config is not None:
                    kwargs["output_config"] = {"format": {"type": "json_schema", "schema": transform_schema(config.output_config.json_schema)}}

                async with client.messages.stream(**kwargs) as stream:
                    async for text in stream.text_stream:
                        print(text, end="", flush=True)
                        assistant_text += text

                print()

                message = await stream.get_final_message()                                                                                                           
                stop_reason = message.stop_reason                                                                                                             
                description = STOP_REASON_DESCRIPTIONS.get(StopReason(stop_reason), "Unknown stop reason.")                                                   
                print(f"\033[94m[StopReason: {stop_reason}] {description}\033[0m")
                if message.stop_sequence:
                    print(f"\033[94mStop sequence: {message.stop_sequence}\033[0m")
                
            except AuthenticationError:
                messages.pop()
                print("\n[ERROR] Authentication failed. Check your ANTHROPIC_API_KEY.")
                sys.exit(1)
            except APIError as e:
                messages.pop()
                print(f"\n[ERROR] API error: {e.message}")
                continue

            messages.append({"role": "assistant", "content": assistant_text})

    except (EOFError, asyncio.CancelledError, KeyboardInterrupt):
        print()
        return


def main():
    parser = argparse.ArgumentParser(
        prog="chat",
        description="Chat with LLM.",
        epilog=(
            "Examples:\n"
            "  python chat.py config.json\n"
            "  python chat.py config.json --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "config",
        metavar="CONFIG_FILE",
        help="Path to the JSON configuration file (required)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print all configuration fields"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    args = parser.parse_args()

    load_dotenv()

    # Load and validate config
    config = load_config(args.config)

    try:
        asyncio.run(run(config, verbose=args.verbose))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
