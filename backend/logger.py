import logging
import logging.handlers
import json
import datetime
import uuid
import os
import time
from contextlib import contextmanager

# Global pipeline context
_run_id = str(uuid.uuid4())
_current_step = None

class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON strings."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).astimezone().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "run_id": getattr(record, "run_id", _run_id),
            "step": getattr(record, "step", _current_step),
        }
        
        # Add any extra attributes added via adapter or extra dict
        # Filter out standard LogRecord attributes
        extra_keys = set(record.__dict__.keys()) - set(logging.LogRecord("", 0, "", 0, "", (), None, None).__dict__.keys()) - {"message", "asctime"}
        if extra_keys:
            extra = {k: getattr(record, k) for k in extra_keys if k not in ["run_id", "step"]}
            if extra:
                log_entry["extra"] = extra

        # Extract extra dictionary passed explicitly via adapter if available
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
             if "extra" not in log_entry:
                 log_entry["extra"] = {}
             log_entry["extra"].update(record.extra_data)

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class ConsoleColorFormatter(logging.Formatter):
    """Formats log records for interactive console output."""
    COLORS = {
        'DEBUG': '\033[94m',      # Blue
        'INFO': '\033[92m',       # Green
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[91m\033[1m' # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        step_info = f"[{getattr(record, 'step', _current_step)}] " if getattr(record, 'step', _current_step) else ""
        message = record.getMessage()
        return f"{color}[{record.levelname}]{self.RESET} {step_info}{message}"


class PipelineLoggerAdapter(logging.LoggerAdapter):
    """Adapter to easily pass step and extra context."""
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        # We store custom extra data in "extra_data" so it doesn't conflict with logging standard extra
        context = {
            "run_id": _run_id,
            "step": _current_step,
        }
        if "extra" in kwargs:
             context["extra_data"] = kwargs.pop("extra")
        
        kwargs["extra"] = context
        return msg, kwargs


def setup_logging(debug=False, log_dir='logs'):
    """Initializes the logging infrastructure."""
    os.makedirs(log_dir, exist_ok=True)
    
    root_logger = logging.getLogger()
    
    # Clear existing handlers if setup is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(ConsoleColorFormatter())
    root_logger.addHandler(console_handler)

    # 2. File Handler (JSON lines, TimedRotatingFileHandler)
    log_file = os.path.join(log_dir, f"pipeline_{datetime.datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG) # Always log DEBUG to file if possible, or follow root logger
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    return get_logger(__name__)


def get_logger(name):
    """Returns a configured logger adapter instance."""
    logger = logging.getLogger(name)
    return PipelineLoggerAdapter(logger, {})


@contextmanager
def timed_step(step_name, description):
    """Context manager for timing pipeline stages and setting step context."""
    global _current_step
    previous_step = _current_step
    _current_step = step_name
    
    logger = get_logger(__name__)
    logger.info(f"Starting step: {description}")
    
    start_time = time.time()
    try:
        yield
    except Exception as e:
        duration_s = round(time.time() - start_time, 2)
        logger.error(f"Step failed after {duration_s}s: {description}", exc_info=True, extra={"duration_s": duration_s})
        raise
    finally:
        duration_s = round(time.time() - start_time, 2)
        logger.info(f"{description} concluído em {duration_s}s", extra={"duration_s": duration_s})
        _current_step = previous_step

