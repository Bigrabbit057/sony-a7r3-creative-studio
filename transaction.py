import sys
from core import SCOPE

def read_values(backend, expected):
    values = {}
    for key, raw in sorted(expected.items()):
        value = backend.readBackup(int(key, 16))
        if len(value) != len(bytes.fromhex(raw)):
            raise RuntimeError(f"Unexpected property length: {key}")
        values[key] = value.hex()
    return values

def guarded_transition(backend, identity, before, changes, record):
    """Execute a caller-validated setting plan; journal and recover exact values."""
    if identity != SCOPE:
        raise ValueError("Device identity mismatch")
    if not changes or any(key not in before for key in changes):
        raise ValueError("Changes must be a nonempty subset of monitored properties")
    for key, raw in changes.items():
        if len(bytes.fromhex(raw)) != len(bytes.fromhex(before[key])):
            raise ValueError(f"Wrong write length: {key}")
    before = dict(before)
    targets = tuple(changes)
    original_values = {key: before[key] for key in targets}
    after = {**before, **changes}
    for index in range(2):
        actual = read_values(backend, before)
        record("preflight", dict(index=index, properties=actual))
        if actual != before:
            changed = [k for k in before if actual[k] != before[k]]
            raise RuntimeError(f"Baseline mismatch; no write: {changed}")
    record("write_intent", dict(changes={key: dict(before=before[key], after=after[key])
                                         for key in targets}, original_baseline=original_values))
    try:
        for key in targets:
            backend.writeBackup(int(key, 16), bytes.fromhex(after[key]))
            record("write_returned", dict(property_id=key))
        actual = read_values(backend, after)
        record("before_sync_readback", dict(properties=actual))
        if actual != after:
            raise RuntimeError("Post-write readback mismatch")
        record("sync_intent", dict(method="upstream syncBackup/saveBackup(0)"))
        backend.syncBackup()
        record("sync_returned", {})
        for index in range(2):
            actual = read_values(backend, after)
            record("post_sync_readback", dict(index=index, properties=actual))
            if actual != after:
                raise RuntimeError("Post-sync readback mismatch")
    except Exception as exc:
        # A journal failure after the camera write must not prevent recovery.
        def recovery_record(event, data):
            try:
                record(event, data)
            except Exception:
                print(f"Recovery log unavailable for {event}", file=sys.stderr, flush=True)
        recovery_record("trial_error", dict(error=f"{type(exc).__name__}: {exc}"))
        try:
            current = {key: backend.readBackup(int(key, 16)).hex() for key in targets}
            if any(current[key] not in (before[key], after[key]) for key in targets):
                raise RuntimeError("Unexpected target bytes; automatic writes stopped")
            changed = [key for key in reversed(targets) if current[key] != before[key]]
            for key in changed:
                recovery_record("rollback_intent", dict(property_id=key, value=before[key]))
                backend.writeBackup(int(key, 16), bytes.fromhex(before[key]))
            if changed:
                backend.syncBackup()
            restored = read_values(backend, before)
            recovery_record("rollback_readback", dict(properties=restored, matches_before=restored == before))
            if restored != before:
                raise RuntimeError("Original captured values not fully restored")
        except Exception as rollback_error:
            recovery_record("rollback_error", dict(error=f"{type(rollback_error).__name__}: {rollback_error}"))
            raise RuntimeError("Trial failed; restoration is NOT confirmed. Inspect journal.") from exc
        raise RuntimeError("Trial failed; original captured values read back unchanged/restored.") from exc
    record("transaction_verified", dict(values={key: after[key] for key in targets},
                                         menu_verified=False, reboot_verified=False))
