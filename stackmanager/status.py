from enum import Enum, auto

STACK_STATUS = "StackStatus"
STACK_NAME = "StackName"


class StackStatus(Enum):
    CREATE_COMPLETE = auto()
    CREATE_FAILED = auto()
    CREATE_IN_PROGRESS = auto()
    DELETE_COMPLETE = auto()
    DELETE_FAILED = auto()
    DELETE_IN_PROGRESS = auto()
    REVIEW_IN_PROGRESS = auto()
    ROLLBACK_COMPLETE = auto()
    ROLLBACK_FAILED = auto()
    ROLLBACK_IN_PROGRESS = auto()
    UPDATE_COMPLETE = auto()
    UPDATE_COMPLETE_CLEANUP_IN_PROGRESS = auto()
    UPDATE_IN_PROGRESS = auto()
    UPDATE_ROLLBACK_COMPLETE = auto()
    UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS = auto()
    UPDATE_ROLLBACK_FAILED = auto()
    UPDATE_ROLLBACK_IN_PROGRESS = auto()

    @classmethod
    def get_status(cls, stack):
        if not stack or STACK_STATUS not in stack:
            raise ValueError('No StackStatus available')

        try:
            return StackStatus[stack[STACK_STATUS]]
        except KeyError:
            raise ValueError(f'Unknown StackStatus {stack[STACK_STATUS]}')

    @classmethod
    def is_status(cls, stack, status):
        return StackStatus.get_status(stack) == status

    @classmethod
    def is_in_progress(cls, stack):
        stack_status = StackStatus.get_status(stack)
        return stack_status in [StackStatus.CREATE_IN_PROGRESS,
                                StackStatus.DELETE_IN_PROGRESS,
                                StackStatus.ROLLBACK_IN_PROGRESS,
                                StackStatus.UPDATE_COMPLETE_CLEANUP_IN_PROGRESS,
                                StackStatus.UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS,
                                StackStatus.UPDATE_ROLLBACK_IN_PROGRESS]

    @classmethod
    def is_deletable(cls, stack):
        return stack and not StackStatus.is_in_progress(stack)

    @classmethod
    def is_creatable(cls, stack):
        return not stack or StackStatus.get_status(stack) == StackStatus.REVIEW_IN_PROGRESS

    @classmethod
    def is_updatable(cls, stack):
        if not stack:
            return False
        stack_status = StackStatus.get_status(stack)
        return stack_status in [StackStatus.CREATE_COMPLETE,
                                StackStatus.UPDATE_COMPLETE,
                                StackStatus.UPDATE_ROLLBACK_COMPLETE]
