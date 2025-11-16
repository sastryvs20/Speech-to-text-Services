"""
logger.py

Default behavior:
- Logs are stored in a directory set by the `LOG_DIR` environment variable
  (or `/home/gcp-admin/Speech-To-Text-Services/Services` if unset).
- Main log file: `transcription_service.log`
- Rotates daily at 10:00 AM IST, archives to `daily_logs`, keeps last 7 days.
- Log format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`

"""

import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, time as dtime
from logging.handlers import TimedRotatingFileHandler
from typing import Protocol, Tuple, List
from zoneinfo import ZoneInfo 

# -----------------------------
# Configuration & Contracts
# -----------------------------

@dataclass(frozen=True)
class LoggerConfig:
    """
    Immutable configuration for the logging system.
    """
    log_dir_env: str = "LOG_DIR"
    default_log_dir: str = "/home/ubuntu/Speech-To-Text-Services/Call_Audit"
    main_log_filename: str = "service.log"
    daily_logs_subdir: str = "daily_logs"
    prune_keep: int = 14
    rotate_when: str = "midnight"
    rotate_interval: int = 1
    rotate_utc: bool = False
    rotate_time_tz: str = "Asia/Kolkata"
    rotate_time_hour: int = 15
    rotate_time_minute: int = 59
    rotate_time_second: int = 0
    date_filename_regex: str = r"^\d{4}-\d{2}-\d{2}(?:_\d+)?\.log$"
    formatter: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter_datefmt: str = "%Y-%m-%d %H:%M:%S"


class FileSystem(Protocol):
    """
    Abstraction over file-system operations (SRP & testability).
    """
    def listdir(self, path: str) -> List[str]: ...
    def exists(self, path: str) -> bool: ...
    def getmtime(self, path: str) -> float: ...
    def move(self, src: str, dst: str) -> None: ...
    def copy2(self, src: str, dst: str) -> None: ...
    def remove(self, path: str) -> None: ...
    def makedirs(self, path: str, exist_ok: bool = True) -> None: ...


# -----------------------------
# Concrete FileSystem
# -----------------------------

class LocalFileSystem:
    def listdir(self, path: str) -> List[str]:
        return os.listdir(path)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def getmtime(self, path: str) -> float:
        return os.path.getmtime(path)

    def move(self, src: str, dst: str) -> None:
        shutil.move(src, dst)

    def copy2(self, src: str, dst: str) -> None:
        shutil.copy2(src, dst)

    def remove(self, path: str) -> None:
        os.remove(path)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        os.makedirs(path, exist_ok=exist_ok)


# -----------------------------
# Helpers
# -----------------------------

class PathResolver:
    
    def __init__(self, cfg: LoggerConfig, fs: FileSystem) -> None:
        self._cfg = cfg
        self._fs = fs

        base_dir = os.getenv(self._cfg.log_dir_env, self._cfg.default_log_dir)
        self._log_dir = base_dir
        self._log_file = os.path.join(self._log_dir, self._cfg.main_log_filename)
        self._daily_logs_dir = os.path.join(self._log_dir, self._cfg.daily_logs_subdir)

        # Preserve original behavior: ensure directories exist at import/initialization time.
        self.ensure_dirs()

    @property
    def log_dir(self) -> str:
        return self._log_dir

    @property
    def log_file(self) -> str:
        return self._log_file

    @property
    def daily_logs_dir(self) -> str:
        return self._daily_logs_dir

    def ensure_dirs(self) -> None:
        self._fs.makedirs(self._log_dir, exist_ok=True)
        self._fs.makedirs(self._daily_logs_dir, exist_ok=True)


class DailyLogPruner:
    """
    Prunes older daily logs, keeping only the newest `keep` files.
    """
    def __init__(self, fs: FileSystem, daily_dir: str, pattern: re.Pattern, keep: int) -> None:
        self._fs = fs
        self._daily_dir = daily_dir
        self._pattern = pattern
        self._keep = keep

    def prune(self) -> None:
        candidates: List[Tuple[float, str]] = []
        for fname in self._safe_listdir(self._daily_dir):
            if self._pattern.match(fname):
                path = os.path.join(self._daily_dir, fname)
                try:
                    candidates.append((self._fs.getmtime(path), path))
                except FileNotFoundError:
                    # File might have been removed between listdir and getmtime
                    pass

        # Sort newest first
        candidates.sort(key=lambda x: x[0], reverse=True)

        for _, path in candidates[self._keep:]:
            try:
                self._fs.remove(path)
            except FileNotFoundError:
                pass
            except Exception:
                # Preserve original "best effort" behavior
                pass

    def _safe_listdir(self, path: str) -> List[str]:
        try:
            return self._fs.listdir(path)
        except FileNotFoundError:
            return []


class DateBasedRotator:

    def __init__(self, fs: FileSystem, daily_dir: str, prune: DailyLogPruner, tz: ZoneInfo) -> None:
        self._fs = fs
        self._daily_dir = daily_dir
        self._prune = prune
        self._tz = tz

    def __call__(self, source: str, dest: str) -> None:
        # Logic preserved exactly from original function
        try:
            ts = self._fs.getmtime(source)
        except FileNotFoundError:
            return

        date_str = datetime.fromtimestamp(ts, tz=self._tz).strftime("%Y-%m-%d")
        final_path = os.path.join(self._daily_dir, f"{date_str}.log")

        if self._fs.exists(final_path):
            suffix = 1
            while self._fs.exists(final_path):
                final_path = os.path.join(self._daily_dir, f"{date_str}_{suffix}.log")
                suffix += 1

        try:
            self._fs.move(source, final_path)
        except FileNotFoundError:
            return
        except Exception:
            try:
                self._fs.copy2(source, final_path)
                self._fs.remove(source)
            except Exception:
                # Preserve original "best effort" behavior
                pass

        self._prune.prune()


class LoggerFactory:
    def __init__(self, cfg: LoggerConfig, fs: FileSystem | None = None) -> None:
        self._cfg = cfg
        self._fs = fs or LocalFileSystem()
        self._paths = PathResolver(cfg, self._fs)

        self._date_pattern = re.compile(self._cfg.date_filename_regex)
        self._pruner = DailyLogPruner(
            fs=self._fs,
            daily_dir=self._paths.daily_logs_dir,
            pattern=self._date_pattern,
            keep=self._cfg.prune_keep
        )
        self._rotator = DateBasedRotator(
            fs=self._fs,
            daily_dir=self._paths.daily_logs_dir,
            prune=self._pruner,
            tz=ZoneInfo(self._cfg.rotate_time_tz),
        )

       
        self._shared_handler = self._build_handler()
        self._shared_handler._is_shared = True  

        root = logging.getLogger()
        if not any(getattr(h, "_is_shared", False) for h in root.handlers):
            root.addHandler(self._shared_handler)
            root.setLevel(logging.INFO)

    def _build_handler(self) -> TimedRotatingFileHandler:
        rotate_time = dtime(
            self._cfg.rotate_time_hour,
            self._cfg.rotate_time_minute,
            self._cfg.rotate_time_second,
            tzinfo=ZoneInfo(self._cfg.rotate_time_tz)
        )
        h = TimedRotatingFileHandler(
            self._paths.log_file,
            when=self._cfg.rotate_when,
            interval=self._cfg.rotate_interval,
            backupCount=0,
            encoding="utf-8",
            utc=self._cfg.rotate_utc,
            atTime=rotate_time
        )
        h.rotator = self._rotator
        h.setFormatter(logging.Formatter(self._cfg.formatter, datefmt=self._cfg.formatter_datefmt))
        return h

    def get_logger(self, name: str = "global_logger", level: int = logging.INFO) -> logging.Logger:
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = True
        for h in list(logger.handlers):
            logger.removeHandler(h)
        return logger



# -----------------------------
# Public API (backward-compatible)
# -----------------------------

__LOGGER_FACTORY = LoggerFactory(LoggerConfig())

def get_logger(name: str = "global_logger", level=logging.INFO) -> logging.Logger:
    return __LOGGER_FACTORY.get_logger(name=name, level=level)