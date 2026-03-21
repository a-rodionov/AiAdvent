import sys
import os
import signal
import asyncio
import argparse
from enum import Enum
from config import load_config, ModelConfig
from dotenv import load_dotenv
from anthropic import AsyncAnthropic, APIError, AuthenticationError, transform_schema


async def run(config: ModelConfig, user_input: str, verbose: bool) -> None:
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
            
        except AuthenticationError:
            messages.pop()
            print("\n[ERROR] Authentication failed. Check your ANTHROPIC_API_KEY.")
            sys.exit(1)
        except APIError as e:
            messages.pop()
            print(f"\n[ERROR] API error: {e.message}")
            sys.exit(1)

        messages.append({"role": "assistant", "content": assistant_text})

    except (EOFError, asyncio.CancelledError, KeyboardInterrupt):
        print()
        return


def main():
    parser = argparse.ArgumentParser(
        prog="single_message",
        description="Send single message to LLM.",
        epilog=(
            "Examples:\n"
            "  python single_message.py config.json \"Some user input\"\n"
            "  python single_message.py config.json \"Some user input\" --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "config",
        metavar="CONFIG_FILE",
        help="Path to the JSON configuration file (required)"
    )

    parser.add_argument(
        "user_input",
        metavar="USER_INPUT",
        help="Some user input text for sending to LLM"
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
        asyncio.run(run(config, args.user_input, verbose=args.verbose))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
