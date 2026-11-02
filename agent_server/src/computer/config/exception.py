class BaseException(Exception):
    def __init__(self, message:str|None=None) -> None:
        super().__init__(message)
        self.message=message

class IntentionallyBlockedServerToolCall(BaseException):
    def __init__(self, message:str="Its a Frontend Tool Call, not a Server Tool Call, Hence not allowed to be called from the Server Node") -> None:
        super().__init__(message)