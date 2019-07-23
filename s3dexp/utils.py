import directio
import fnmatch
import os


def recursive_glob(base_dir, pattern):
    for root, _, filenames in os.walk(base_dir):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def directio_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
    content = directio.read(fd, 1024*1024)  # FIXME
    os.close(fd)
    return content