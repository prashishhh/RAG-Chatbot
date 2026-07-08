import logging
import sys

from pythonjsonlogger import json


def configure_logging(app_env: str, log_level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Parse log level safely
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = json.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    if app_env.lower() in {"local", "development", "dev", "test"}:
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
