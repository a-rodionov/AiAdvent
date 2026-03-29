import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure the workspace root is on sys.path so that `server` resolves to the
# server/ package (not this script), allowing `from server.X` imports to work
# both here and in modules shared with client.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from dotenv import load_dotenv

from server.app_factory import create_app
from server.application.domain.model.completion import format_completion_config
from server.common.config_loader import get_server_config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="server",
        description="Chat server.",
    )
    parser.add_argument("server_config", metavar="SERVER_CONFIG_FILE")
    args = parser.parse_args()

    server_config = get_server_config(args.server_config)
    load_dotenv()

    logging.basicConfig(
        level=getattr(logging, server_config.log_level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    os.environ.setdefault("ANY_LLM_UNIFIED_EXCEPTIONS", "1")

    logger = logging.getLogger("server")
    logger.info(format_completion_config(server_config.default_completion_config))

    app = create_app(server_config)
    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()
