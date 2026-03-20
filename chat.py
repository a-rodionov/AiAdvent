import os
import argparse
from config import load_config, ModelConfig
from dotenv import load_dotenv
from anthropic import Anthropic

def run(config: ModelConfig, verbose: bool) -> None:
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

    client = Anthropic(
        # This is the default and can be omitted
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    print("Press Ctrl+C or Ctrl+D to exit.\n")
    system_prompt = input("Enter system prompt if needed: ")
    messages = []
    while True:
        try:
            user_input = input("User: ")
            messages.append({"role": "user", "content": user_input})

            response = client.messages.create(
                system=system_prompt,
                max_tokens=config.max_tokens,
                messages=messages,
                model=config.model,
                temperature=config.temperature,
                top_k=config.top_k
            )

            assistant_text = ""
            for content in response.content:
                if "text" == content.type:
                    print("Model: ", content.text)
                    assistant_text += content.text
                else:
                    print("Model returned unsupported type of content: ", content.type)

            messages.append({"role": "assistant", "content": assistant_text})

        except KeyboardInterrupt:
            break
        except EOFError:
            break


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

    run(config, verbose=args.verbose)


if __name__ == "__main__":
    main()
