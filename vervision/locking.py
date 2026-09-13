"""Small cross-process writer lock; readers keep using ordinary Markdown files."""
from contextlib import contextmanager
from functools import wraps
import hashlib
import os
import tempfile
from pathlib import Path


@contextmanager
def project_lock(root):
    key = hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f"vervision-{key}.lock"
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def writer(function):
    @wraps(function)
    def wrapped(root, *args, **kwargs):
        with project_lock(root):
            return function(root, *args, **kwargs)
    return wrapped
