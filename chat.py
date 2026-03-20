import sys
import os
import signal
import asyncio
import argparse
from config import load_config, ModelConfig
from dotenv import load_dotenv
from anthropic import AsyncAnthropic, APIError, AuthenticationError


async def run(config: ModelConfig, verbose: bool) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)
    print("Configuration loaded successfully!\n")

    if verbose:
        print("=== Full Configuration ===")
        print(f"  {'model':<20} {config.model}")
        print(f"  {'max_tokens':<20} {config.max_tokens}")
        print(f"  {'temperature':<20} {config.temperature}")
        print(f"  {'top_k':<20} {config.top_k}")
        print(f"  {'top_p':<20} {config.top_p}")
    else:
        print(f"Model : {config.model}")
        print(f"Tokens: {config.max_tokens}")
        print(f"Temp  : {config.temperature}")
        print("\nTip: use --verbose to see all fields.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)

    print("Press Ctrl+C or Ctrl+D to exit.\n")
    try:
        system_prompt = input("Enter system prompt if needed: ")
        messages = []
        while True:
            user_input = input("User: ")
            if not user_input.strip():
                continue

            messages.append({"role": "user", "content": user_input})

            try:
                assistant_text = ""
                print("Model: ", end="", flush=True)
                async with client.messages.stream(
                    system=system_prompt,
                    max_tokens=config.max_tokens,
                    messages=messages,
                    model=config.model,
                    temperature=config.temperature,
                    top_k=config.top_k
                ) as stream:
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
