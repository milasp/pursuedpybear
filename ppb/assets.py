"""
The asset loading system.
"""

import concurrent.futures
import logging
import threading

import ppb.vfs as vfs
from ppb.systems import System

__all__ = 'Asset', 'AssetLoadingSystem',

logger = logging.getLogger(__name__)


class Asset:
    """
    A resource to be loaded from the filesystem and used.

    Meant to be subclassed.
    """
    def __init__(self, name):
        self.name = str(name)
        self._finished = threading.Event()
        _hint(self.name, self._finished_background)

    def __repr__(self):
        return f"<{type(self).__name__} name={self.name!r}>"

    def _finished_background(self, fut):
        # Internal
        # Called in background thread
        try:
            try:
                raw = fut.result()
            except FileNotFoundError:
                if hasattr(self, 'file_missing'):
                    logger.warning("File not found: %r", self.name)
                    self._data = self.file_missing()
                else:
                    raise
            else:
                self._data = self.background_parse(raw)
        except Exception as exc:
            # Save unhandled exceptions to be raised in the main thread
            self._raise_error = exc
        finally:
            # This always needs to happen so the main thread isn't just blocked
            self._finished.set()

    def background_parse(self, data: bytes):
        """
        Takes the data loaded from the file and returns the parsed data.

        Subclasses probably want to override this.

        Called in the background thread.
        """
        return data

    def is_loaded(self):
        """
        Returns if the data has been loaded and parsed.
        """
        return self._finished.is_set()

    def load(self, timeout: float = None):
        """
        Gets the parsed data.

        Will block until the data is loaded.
        """
        if _hint is _default_hint:
            logger.warn(f"Waited on {self!r} before the engine began")
        self._finished.wait(timeout)
        if hasattr(self, '_raise_error'):
            raise self._raise_error
        else:
            return self._data


class AssetLoadingSystem(System):
    def __init__(self, **_):
        self._executor = concurrent.futures.ThreadPoolExecutor()
        self._queue = {}  # maps names to futures

    def __enter__(self):
        # 1. Register ourselves as the hint provider
        global _hint, _backlog
        assert _hint is _default_hint
        _hint = self._hint

        # 2. Grab-n-clear the backlog (atomically?)
        queue, _backlog = _backlog, []

        # 3. Process the backlog
        for filename, callback in queue:
            self._hint(filename, callback)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset the hint provider
        global _hint
        _hint = _default_hint

    def _hint(self, filename, callback=None):
        if filename not in self._queue:
            self._queue[filename] = self._executor.submit(self._load, filename)
        if callback is not None:
            self._queue[filename].add_done_callback(callback)

    @staticmethod
    def _load(filename):
        with vfs.open(filename) as file:
            return file.read()


_backlog = []


def _default_hint(filename, callback=None):
    _backlog.append((filename, callback))


_hint = _default_hint
