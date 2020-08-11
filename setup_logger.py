import logging
# logging.basicConfig(level=logging.DEBUG)
# def get_logger():
#     # Create a custom logger
#     logger = logging.getLogger('e2e_output.log')
#
#     # logger = logging.basicConfig(filename='e2e_output.log', filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     # Create handlers
#     f_handler = logging.FileHandler('e2e_output.log')
#     # f_handler = logging.FileHandler(__name__)
#     f_handler.setLevel(logging.WARNING)
#
#     # Create formatters and add it to handlers
#     f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.setFormatter(f_format)
#
#     # Add handlers to the logger
#     logger.addHandler(f_handler)
#     return logger


def get_logger(name=__name__):
    '''Create custom loggers for multiple modules

    Assumes logs should be written to a file.

    Keyword arguments:
    ------------------
    name: str
        name of file to write logs to

    Returns:
    --------
    logging object
    '''
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        f_handler = logging.FileHandler(name)
        f_handler.setLevel(logging.WARNING)

        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)

        logger.addHandler(f_handler)
    return logger

def default_logger(name=__name__):
    logging.basicConfig(filename=name, filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    return logging
