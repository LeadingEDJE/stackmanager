import pytest
from stackmanager.status import StackStatus, STACK_STATUS


def test_is_status():
    assert StackStatus.is_status({STACK_STATUS: StackStatus.CREATE_COMPLETE.name}, StackStatus.CREATE_COMPLETE)
    assert not StackStatus.is_status({STACK_STATUS: StackStatus.CREATE_COMPLETE.name}, StackStatus.CREATE_FAILED)


def test_is_status_missing_stack():
    with pytest.raises(ValueError, match='No StackStatus available'):
        StackStatus.is_status(None, StackStatus.CREATE_COMPLETE)


def test_is_status_missing_status():
    with pytest.raises(ValueError, match='No StackStatus available'):
        StackStatus.is_status({}, StackStatus.CREATE_COMPLETE)


def test_is_status_invalid_status():
    with pytest.raises(ValueError, match='Unknown StackStatus UNKNOWN'):
        StackStatus.is_status({STACK_STATUS: 'UNKNOWN'}, StackStatus.CREATE_COMPLETE)


def test_is_creatable():
    assert StackStatus.is_creatable(None)
    assert StackStatus.is_creatable({STACK_STATUS: StackStatus.REVIEW_IN_PROGRESS.name})
    assert not StackStatus.is_creatable({STACK_STATUS: StackStatus.CREATE_COMPLETE.name})


def test_is_updatable():
    assert StackStatus.is_updatable({STACK_STATUS: StackStatus.CREATE_COMPLETE.name})
    assert StackStatus.is_updatable({STACK_STATUS: StackStatus.UPDATE_COMPLETE.name})
    assert StackStatus.is_updatable({STACK_STATUS: StackStatus.UPDATE_ROLLBACK_COMPLETE.name})
    assert StackStatus.is_updatable({STACK_STATUS: StackStatus.IMPORT_COMPLETE.name})
    assert StackStatus.is_updatable({STACK_STATUS: StackStatus.IMPORT_ROLLBACK_COMPLETE.name})

    assert not StackStatus.is_updatable({STACK_STATUS: StackStatus.UPDATE_IN_PROGRESS.name})
