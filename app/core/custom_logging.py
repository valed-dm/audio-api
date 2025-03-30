"""Custom logging module refactored for best practices."""

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
    # Fallback for systems without Colorama
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

    def init():
        """Dummy init function for systems without colorama."""
        pass  # No initialization needed for the fallback


# Use environment variables or a config file for settings instead of directly importing.
# Example using environment variables (adjust as needed):
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()  # Default to INFO
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE_NAME = os.getenv("LOG_FILE", "app.log")
LOG_FILE_SIZE_MB = int(os.getenv("LOG_FILE_SIZE_MB", "10"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Define project-level loggers, available globally through import
logger = logging.getLogger(__name__)  # Standard synchronous logger
async_logger = None  # Async logger (initialized later)

# Add a guard to prevent duplicate configuration
_logging_configured = False


class ColoredFormatter(logging.Formatter):
    """A logging formatter that adds colors to the output based on the log level."""

    COLOR_CODES: ClassVar[dict[int, str]] = {
        logging.DEBUG: f"{Fore.YELLOW}",
        logging.INFO: f"{Fore.GREEN}",
        logging.WARNING: f"{Fore.BLUE}",
        logging.ERROR: f"{Fore.RED}",
        logging.CRITICAL: f"{Fore.RED}{Style.BRIGHT}",
    }
    RESET: ClassVar[str] = Style.RESET_ALL

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        color_code = self.COLOR_CODES.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color_code}{message}{self.RESET}"


class CleanFormatter(logging.Formatter):
    """A logging formatter that removes ANSI escape codes from the output."""

    ANSI_REGEX: ClassVar[re.Pattern[str]] = re.compile(r"\x1b\[[0-9;]*m")

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, removing ANSI escape codes."""
        message = super().format(record)
        return self.ANSI_REGEX.sub("", message)


def configure_logging(
    log_level: str = LOG_LEVEL,
    log_dir: str = LOG_DIR,
    log_file_name: str = LOG_FILE_NAME,
    log_file_size_mb: int = LOG_FILE_SIZE_MB,
    log_backup_count: int = LOG_BACKUP_COUNT,
) -> None:
    """
    Configures the logging system with both console and file handlers.

    Args:
        log_level: The logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_dir: The directory where log files will be stored.
        log_file_name: The name of the log file.
        log_file_size_mb: The maximum size of each log file in megabytes.
        log_backup_count: The number of backup log files to keep.
    """
    global logger
    global async_logger  # Allow modification of global async logger
    global _logging_configured

    if _logging_configured:  # Check if already configured
        return

    log_level = log_level.upper()  # Ensure uppercase for level comparison
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logger.setLevel(numeric_level)  # Set the level for the synchronous logger

    # Define formatters
    console_formatter = ColoredFormatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_formatter = CleanFormatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # File handler setup with robust error handling.
    log_file_path = Path(log_dir) / log_file_name
    try:
        log_file_path.parent.mkdir(
            parents=True, exist_ok=True
        )  # Ensure log directory exists
    except OSError as e:
        logger.error(f"Failed to create log directory: {e}", exc_info=True)
        return  # Abort configuration if directory creation fails

    try:
        rotating_file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=log_file_size_mb * 1024 * 1024,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        rotating_file_handler.setFormatter(file_formatter)
    except OSError as e:
        logger.error(f"Failed to create rotating file handler: {e}", exc_info=True)
        return  # Abort configuration if handler creation fails

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(rotating_file_handler)

    # Initialize AsyncLogger *after* basic configuration
    async_logger = AsyncLogger(logger)
    logger.info(
        f"Logging configured to level {log_level} with file output to {log_file_path}"
    )
    _logging_configured = True  # Set the flag


class AsyncLogger:
    """Asynchronous logger that wraps a standard logger and executes log calls in a thread pool."""

    def __init__(self, logger: logging.Logger, max_workers: int = 1):
        """
        Initializes the AsyncLogger.

        Args:
            logger: The standard logging.Logger instance to wrap.
            max_workers: The maximum number of threads in the thread pool.
        """
        self._logger = logger
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="AsyncLogger"
        )

    async def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """
        Asynchronously logs a message at the specified level.

        Args:
            level: The logging level (e.g., logging.INFO, logging.ERROR).
            msg: The message to log.
            *args: Arguments to pass to the logging function.
            **kwargs: Keyword arguments to pass to the logging function.
        """
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                self._executor, lambda: self._logger.log(level, msg, *args, **kwargs)
            )
        except RuntimeError as e:  # Specific Exception
            sys.stderr.write(f"Error during asynchronous logging: {e}\n")

    async def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Asynchronously logs a debug message."""
        await self._log(logging.DEBUG, msg, *args, **kwargs)

    async def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Asynchronously logs an info message."""
        await self._log(logging.INFO, msg, *args, **kwargs)

    async def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Asynchronously logs a warning message."""
        await self._log(logging.WARNING, msg, *args, **kwargs)

    async def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Asynchronously logs an error message."""
        await self._log(logging.ERROR, msg, *args, **kwargs)

    async def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Asynchronously logs a critical message."""
        await self._log(logging.CRITICAL, msg, *args, **kwargs)

    def shutdown(self, wait: bool = True) -> None:
        """Shuts down the thread pool executor."""
        self._executor.shutdown(wait=wait)

    async def __aenter__(self):
        """For use in async with statements."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Shutdown executor on exit"""
        self.shutdown(wait=True)


# Configure logging immediately on module import (or where appropriate in the application startup).
# configure_logging()   # DO NOT CALL HERE.  Called in main.py
# logger.info("Logging module loaded") # Example usage of standard logger

T = TypeVar("T", bound=Awaitable[Any])


def log_execution(
    level: int = logging.INFO, track_time: bool = True, show_args: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    A decorator that logs the execution of an asynchronous function.

    Args:
        level: The logging level (default: logging.INFO).
        track_time: Whether to track and log the execution time (default: True).
        show_args: Whether to include function arguments in the log (default: False).

    Returns:
        A decorator that wraps the function.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """The actual decorator."""

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            """The wrapper function."""
            global logger
            global async_logger  # Access global async logger

            # Get the filename and line number of the caller
            try:
                frame = inspect.currentframe()
                if frame and frame.f_back:
                    # Cover all known cases of frame inspection issues
                    code = frame.f_back.f_code
                    filename = Path(code.co_filename).name
                    lineno = frame.f_back.f_lineno
                else:
                    filename, lineno = "unknown", 0
            except (AttributeError, TypeError, ValueError) as e:
                logger.debug(
                    f"Failed to inspect frame: {type(e).__name__}: {e}", exc_info=True
                )
                filename, lineno = "unknown", 0
            finally:
                del frame  # Prevent reference cycles.

            func_name = func.__name__
            arg_string = (
                f"({', '.join(map(repr, args))})" if show_args else ""
            )  # Use repr for better argument representation

            start_message = f"START {filename}:{lineno} - {func_name}{arg_string}"
            if async_logger:
                await async_logger.info(start_message)
            else:
                logger.info(start_message)

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                end_time = time.perf_counter()
                elapsed_time = end_time - start_time

                if track_time:
                    elapsed_message = f"FINISH {filename}:{lineno} - {func_name}{arg_string} in {elapsed_time:.4f}s"
                    if async_logger:
                        await async_logger.info(elapsed_message)
                    else:
                        logger.info(elapsed_message)

                return result
            except Exception as e:
                end_time = time.perf_counter()
                elapsed_time = end_time - start_time
                error_message = f"ERROR {filename}:{lineno} - {func_name}{arg_string} after {elapsed_time:.4f}s: {e!s}"
                if async_logger:
                    await async_logger.error(error_message, exc_info=True)
                else:
                    logger.error(error_message, exc_info=True)
                raise

        return wrapper

    return decorator
