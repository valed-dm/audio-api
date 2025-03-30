"""Custom logging module to be refactored"""

import asyncio
import inspect
import logging
import logging.handlers
import os
import re
import sys
import time
from collections.abc import Awaitable
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import Any
from typing import ClassVar
from typing import TypeVar

try:
    from colorama import Fore
    from colorama import Style
    from colorama import init

    init()
except ImportError:

    class Fore:
        BLACK = "\033[30m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        CYAN = "\033[36m"
        WHITE = "\033[37m"
        RESET = "\033[39m"

    class Style:
        DIM = "\033[2m"
        NORMAL = "\033[22m"
        BRIGHT = "\033[1m"
        RESET_ALL = "\033[0m"


from app.core.config import settings


class EnhancedColorFormatter(logging.Formatter):
    COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: Fore.YELLOW,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.BLUE,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
    RESET: ClassVar[str] = Style.RESET_ALL

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


class SafeFileFormatter(logging.Formatter):
    """Strict ANSI code removal for file logging"""

    ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*m")

    def format(self, record):
        message = super().format(record)
        return self.ANSI_REGEX.sub("", message)


def setup_logging():
    """Configure logging handlers and levels with console colors and file rotation"""
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger()
    logger.propagate = False
    logger.setLevel(settings.LOG_LEVEL)

    # Clear existing handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(EnhancedColorFormatter(fmt, datefmt))
    logger.addHandler(console_handler)

    # File handler with error handling
    try:
        log_dir = (Path(__file__).parent.parent / "logs").resolve()
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            str(log_dir / "app.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(SafeFileFormatter(fmt, datefmt))
        logger.addHandler(file_handler)
    except OSError as e:
        logger.error(f"Failed to initialize file logging: {e}", exc_info=True)
        # Continue with just console logging


class AsyncLogger:
    """Thread-safe async logging with dedicated executor"""

    def __init__(self, logger):
        self._logger = logger
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="AsyncLogger"
        )

    async def _log(self, level: int, msg: str, *args, **kwargs):
        try:
            await asyncio.get_event_loop().run_in_executor(
                self._executor, lambda: self._logger.log(level, msg, *args, **kwargs)
            )
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"Logging failed: {e!s}\n")

    async def debug(self, msg, *args, **kwargs):
        await self._log(logging.DEBUG, msg, *args, **kwargs)

    async def info(self, msg, *args, **kwargs):
        await self._log(logging.INFO, msg, *args, **kwargs)

    async def warning(self, msg, *args, **kwargs):
        await self._log(logging.WARNING, msg, *args, **kwargs)

    async def error(self, msg, *args, **kwargs):
        await self._log(logging.ERROR, msg, *args, **kwargs)

    async def critical(self, msg, *args, **kwargs):
        await self._log(logging.CRITICAL, msg, *args, **kwargs)


# Initialize logging system
setup_logging()
logger = logging.getLogger(__name__)
async_logger = AsyncLogger(logger)

T = TypeVar("T", bound=Awaitable[Any])


def log_execution(
    level: int = logging.INFO, track_time: bool = True, show_args: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Enhanced async function logger with execution tracking"""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Safe source inspection
            try:
                frame = inspect.currentframe()
                if frame and frame.f_back:
                    try:
                        filename = os.path.relpath(frame.f_back.f_code.co_filename)
                    except (ValueError, TypeError):  # os.path.relpath() exceptions
                        filename = frame.f_back.f_code.co_filename  # Fallback to raw path
                    lineno = frame.f_back.f_lineno
                else:
                    filename, lineno = "unknown", 0
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Frame inspection failed: {type(e).__name__}: {e}")
                filename, lineno = "unknown", 0
            finally:
                del frame  # Important! Prevents reference cycles

            # Prepare log messages
            func_name = func.__name__
            arg_str = f"({', '.join(map(str, args))}" if show_args else ""

            start_msg = f"{filename}:{lineno} → {func_name}{arg_str}"
            await async_logger._log(level, f"START  {start_msg}")

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)

                if track_time:
                    elapsed = time.perf_counter() - start_time
                    time_msg = f" in {elapsed:.3f}s"
                    await async_logger._log(level, f"FINISH {start_msg}{time_msg}")
                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time if track_time else 0
                err_msg = f"FAILED {start_msg} after {elapsed:.3f}s: {e!s}"
                await async_logger.error(err_msg)
                raise

        return wrapper

    return decorator
