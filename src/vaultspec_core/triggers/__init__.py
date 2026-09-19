"""Declarative lifecycle triggers for vaultspec-core events.

Loads YAML definitions from ``.vaultspec/triggers/``, validates against
:data:`SUPPORTED_EVENTS`, and executes shell actions with re-entrancy protection
and a 60-second timeout. Key exports: :func:`load_triggers`,
:func:`fire_triggers`; data classes :class:`Trigger`, :class:`TriggerAction`,
:class:`TriggerResult`. Invoked by :mod:`vaultspec_core.cli.root` after
install/sync.

Distinct from :mod:`vaultspec_core.core.provider_hooks`, which renders
agent-runtime *hooks* into each provider's native config. These are vaultspec's
own lifecycle events, fired inside the vaultspec runtime; this system was
formerly reached as ``spec hooks``, which is now the provider surface.

Execution is gated on the operator consent ledger in :mod:`.trust`, whose
:func:`~.trust.grant`, :func:`~.trust.revoke`, :func:`~.trust.is_trusted` and
:func:`~.trust.partition_by_trust` are re-exported here for the CLI surfaces
that ask for consent and report it.
"""

from .engine import SUPPORTED_EVENTS as SUPPORTED_EVENTS
from .engine import Trigger as Trigger
from .engine import TriggerAction as TriggerAction
from .engine import TriggerResult as TriggerResult
from .engine import fire_triggers as fire_triggers
from .engine import load_triggers as load_triggers
from .trust import grant as grant
from .trust import granted_digests as granted_digests
from .trust import is_trusted as is_trusted
from .trust import partition_by_trust as partition_by_trust
from .trust import revoke as revoke
from .trust import trigger_digest as trigger_digest
from .trust import trust_file_path as trust_file_path
