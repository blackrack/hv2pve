class ContextLogger:
    def __init__(self, logger):
        self.logger = logger
        self.context_stack = []

    def add(self, context):

        self.context_stack.append(context)

    def back(self):

        if self.context_stack:
            self.context_stack.pop()

    def log(self, level, message, *args):
        context_str = " ".join(self.context_stack)
        full_message = f"{context_str} {message}" if context_str else message
        self.logger.log(level, full_message, *args)
