import sys
import os
import signal
import asyncio
import argparse
import logging
import uuid
from chat_config import get_chat_config
from completion_config import CompletionConfigFileAdapter, format_completion_config
from model_pricing import ModelPricing
from model_pricing_adapter import ModelPricingFileAdapter
from dotenv import load_dotenv
from any_llm import AnyLLM, AuthenticationError, AnyLLMError
from llm_adapter import LlmAdapter, StopReason
from session import Session, SessionTextChunkEvent, SessionCompletionDoneEvent, TokensCost, SessionStatistics


STOP_REASON_DESCRIPTIONS = {
    StopReason.STOP: "The model reached a natural stopping point.",
    StopReason.LENGTH: "We exceeded the requested max_tokens or the model's maximum.",
    StopReason.TOOL_CALLS: "The model invoked one or more tools.",
    StopReason.CONTENT_FILTER: "When streaming classifiers intervene to handle potential policy violations.",
}


class _ColorFormatter(logging.Formatter):
    _COLORS = {
        logging.INFO: "\033[94m",
        logging.ERROR: "\033[91m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{self._RESET}" if color else message


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_ColorFormatter("%(message)s"))

logger = logging.getLogger(__name__)
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def _log_stats(label: str, stats: SessionStatistics) -> None:
    logger.info(label)
    for field, value in stats.tokens_usage.model_dump().items():
        logger.info(f"    {field}: {value}")
    if stats.tokens_cost is not None:
        for field, value in stats.tokens_cost.model_dump().items():
            logger.info(f"    {field} cost: ${value:.8f}")


async def run(session: Session) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)

    logger.info(format_completion_config(session.completion_config))

    try:
        while True:
            user_input = input("User: ")
            if not user_input.strip():
                continue

            try:
                sys.stdout.write("Model: ")
                sys.stdout.flush()

                async for event in session.acompletion(user_input, is_stream_prefered=True):
                    if isinstance(event, SessionTextChunkEvent):
                        sys.stdout.write(event.text)
                        sys.stdout.flush()
                    elif isinstance(event, SessionCompletionDoneEvent):
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        description = STOP_REASON_DESCRIPTIONS.get(event.stop_reason, "Unknown stop reason.")
                        logger.info("Response:")
                        logger.info(f"    StopReason: {event.stop_reason}. {description}")
                        logger.info(f"    Elapsed time: {event.elapsed_s:.0f}s")
                        _log_stats("    Tokens usage:", SessionStatistics(
                            tokens_usage=event.tokens_usage,
                            tokens_cost=event.tokens_cost,
                        ))
                        if session.statistics:
                            logger.info("Session:")
                            for key, stats in session.statistics.items():
                                provider, model = key.split(",", 1)
                                _log_stats(f"  {provider}/{model}:", stats)

            except AuthenticationError:
                logger.error("Authentication failed. Check your ANTHROPIC_API_KEY.")
                sys.exit(1)
            except AnyLLMError as e:
                logger.error(f"API error: {e.message}")
                continue

    except (EOFError, asyncio.CancelledError, KeyboardInterrupt):
        sys.stdout.write("\n")
        sys.stdout.flush()
        return


def main():
    parser = argparse.ArgumentParser(
        prog="chat",
        description="Chat with LLM.",
        epilog=(
            "Examples:\n"
            "  python chat.py chat_config.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "chat_config",
        metavar="CHAT_CONFIG_FILE",
        help="Path to the JSON configuration file (required)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    args = parser.parse_args()
    load_dotenv()
    chat_config = get_chat_config(args.chat_config)

    logging.basicConfig(
        level=getattr(logging, chat_config.log_level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    completion_config = CompletionConfigFileAdapter(chat_config.default_completion_config_path).create_completion_config()
    model_pricing = ModelPricing.from_dtos(
        ModelPricingFileAdapter(chat_config.models_pricing_path).get_all_pricing_dtos())

    os.environ.setdefault("ANY_LLM_UNIFIED_EXCEPTIONS", "1")
    llm = LlmAdapter(completion_config.provider)

    session = Session.create(llm, str(uuid.uuid4()), model_pricing, completion_config)

    try:
        asyncio.run(run(session))
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
