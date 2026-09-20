import pytest
from trainer.commands import CommandInbox


def test_partial_messages_wait_for_newline_and_preserve_order():
    inbox = CommandInbox()
    assert inbox.feed(b'{"schema_version":1,"command":"pa') == []
    assert inbox.feed(b'use"}\n{"schema_version":1,"command":"reset"}\n') == ['pause', 'reset']


@pytest.mark.parametrize('message', [b'[]\n', b'{"schema_version":2,"command":"stop"}\n',
                                    b'{"schema_version":1,"command":"delete"}\n'])
def test_invalid_commands_are_rejected(message):
    with pytest.raises(ValueError):
        CommandInbox().feed(message)


def test_oversized_input_does_not_grow_without_bound():
    inbox = CommandInbox()
    with pytest.raises(ValueError):
        inbox.feed(b'x' * 65537)
    assert inbox.buffer == b''
