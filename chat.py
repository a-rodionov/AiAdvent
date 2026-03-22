import sys
import os
import signal
import asyncio
import argparse
import time
from enum import Enum
from chat_config import ChatConfig, ChatConfigFileAdapter
from conversation_config import ConversationConfig, ConversationConfigFileAdapter, format_conversation_config
from model_pricing import ModelPricingFileAdapter, format_pricing_report
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


async def run(conversation_config: ConversationConfig, model_pricing: ModelPricing, verbose: bool) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)

    if verbose:
        print(f"\033[94m{format_conversation_config(conversation_config)}\033[0m")
        

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)

    try:
        messages = []
        input_tokens = 0
        output_tokens = 0
        while True:
            user_input = input("User: ")
            if not user_input.strip():
                continue

            messages.append({"role": "user", "content": user_input})

            try:
                assistant_text = ""
                print("Model: ", end="", flush=True)
                kwargs = {
                    "max_tokens": conversation_config.max_tokens,
                    "messages": messages,
                    "model": conversation_config.model,
                }
                if conversation_config.system_prompt:
                    kwargs["system"] = conversation_config.system_prompt
                if conversation_config.temperature is not None:
                    kwargs["temperature"] = conversation_config.temperature
                if conversation_config.top_k is not None:
                    kwargs["top_k"] = conversation_config.top_k
                if conversation_config.temperature is None and conversation_config.top_p is not None:
                    kwargs["top_p"] = conversation_config.top_p
                if conversation_config.stop_sequences is not None:
                    kwargs["stop_sequences"] = conversation_config.stop_sequences
                if conversation_config.output_config is not None:
                    kwargs["output_config"] = {"format": {"type": "json_schema", "schema": transform_schema(conversation_config.output_config.json_schema)}}

                start_time = time.monotonic()
                async with client.messages.stream(**kwargs) as stream:
                    async for text in stream.text_stream:
                        print(text, end="", flush=True)
                        assistant_text += text
                print()

                message = await stream.get_final_message()
                if verbose:
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    model_pricing.estimate(base_input_tokens = message.usage.input_tokens, output_tokens = message.usage.output_tokens)
                    stop_reason = message.stop_reason
                    description = STOP_REASON_DESCRIPTIONS.get(StopReason(stop_reason), "Unknown stop reason.")
                    print(f"\033[94m[StopReason: {stop_reason}] {description}\033[0m")
                    if message.stop_sequence:
                        print(f"\033[94mStop sequence: {message.stop_sequence}\033[0m")
                    print(f"\033[94m[Response elapsed time: {elapsed_ms:.0f} ms]\033[0m")
                    print(f"\033[94m{format_pricing_report(model_pricing.get_report())}\033[0m")
                
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
            "  python chat.py chat_config.json\n"
            "  python chat.py chat_config.json --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "chat_config",
        metavar="CHAT_CONFIG_FILE",
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

    chat_config_file_adapter = ChatConfigFileAdapter(args.chat_config)
    chat_config = chat_config_file_adapter.create_chat_config()
    conversation_config_file_adapter = ConversationConfigFileAdapter(chat_config.default_conversation_config_path)
    conversation_config = conversation_config_file_adapter.create_conversation_config()
    model_pricing_file_adapter = ModelPricingFileAdapter(chat_config.models_pricing_path)
    model_pricing = model_pricing_file_adapter.create_model_pricing(conversation_config.model)

    try:
        asyncio.run(run(conversation_config, model_pricing, verbose=args.verbose))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
