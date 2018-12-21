import logging


__all__ = [
    'logger',
]

logger = logging.getLogger('jkg-downloader')
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - '
                              '[%(module)s - %(filename)s - %(funcName)s - %(lineno)d]:\n'
                              ' %(message)s',
                              datefmt='%Y-%m-%d-%H:%M:%S')

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)
