"""CustomTkinter views for Amazon Mail Reader."""

from .accounts import AccountsViewMixin
from .inbox import InboxViewMixin
from .payments import PaymentsViewMixin
from .settings import SettingsViewMixin
from .shell import ShellViewMixin

__all__ = [
    "AccountsViewMixin",
    "InboxViewMixin",
    "PaymentsViewMixin",
    "SettingsViewMixin",
    "ShellViewMixin",
]

