import logging, argparse, json


LOG_LEVELS = {0: logging.NOTSET, 1: logging.INFO, 2: logging.DEBUG}


class ContextLogger:
    def __init__(self, logger, verbose):
        self.logger = logger
        self.context_stack = []

        if verbose != 0:
            logging.basicConfig(
                format="%(asctime)s %(levelname)-8s %(message)s",
                level=LOG_LEVELS[verbose],
                datefmt="%Y-%m-%d %H:%M:%S",
            )

    def add(self, context):

        self.context_stack.append(context)
        return self

    def back(self):

        if self.context_stack:
            self.context_stack.pop()

        return self

    def log(self, level, message, *args):
        context_str = " ".join(self.context_stack)
        full_message = f"{context_str} {message}" if context_str else message
        self.logger.log(level, full_message, *args)
        return self
