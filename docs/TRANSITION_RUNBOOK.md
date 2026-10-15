# Paper-ledger operation and recovery

This runbook applies only to the local, hypothetical, single-decision-date lab. No broker connection, outbound order, tax filing or real cash movement exists.

## Reproduce the evidence

From the repository root in the full Python 3.11 hash-locked environment:

```bash
python -m pytest tests/test_transition_lab.py -q -W error
python run_transition_lab.py --no-write
```

The runner uses a temporary SQLite journal and checks all seven budget scenarios, eight financial/chronology faults and six operating steps. It closes database handles explicitly on Windows as well as Linux. To deliberately rebuild the saved hypothetical evidence and view:

```bash
python run_transition_lab.py
python build_transition_dashboard.py
python -m http.server 4188 --directory docs
```

Open `http://127.0.0.1:4188/transition-lab.html`. The builder refuses stale source fingerprints or a failed baseline/incident receipt. This is separate from the original empirical study and its release guard.

## Event contract

Every event requires a nonblank `event_id`, provenance `source`, type and `settled_on` equal to the snapshot decision date. The caller supplies the expected integer state revision. The initial cash/cost policy is persisted separately from submitted plans.

- **Cash flow:** apply only to the named account; reject unknown accounts, future/backdated settlement and overdrafts. Record the flow separately from investment P&L.
- **Split:** adjust all affected lot quantities and per-share bases, with the corresponding price adjustment. Preserve market value and aggregate cost basis. Existing plans become stale because their snapshot fingerprint changes.
- **Transition:** independently validate the plan against current state and stored policy. Record new lots, remaining quantities, cash, cumulative modeled tax reserves and the remaining tax budget. New-lot tax rates must be explicit inputs, not guessed from holding periods.

## Recovery decisions

| Condition | Required behavior |
|---|---|
| Exact same event ID and payload arrive again | Return the original result; no new event or balance mutation. |
| Same ID with different payload | Block with `conflicting_idempotency_key`. Do not silently replace the committed record. |
| New event carries an old revision | Block with `stale_state_version`. Reload state and recompute if appropriate. |
| Plan references an older source snapshot | Block with `source_snapshot_fingerprint`, even if its dollar totals look plausible. |
| Exception after writes but before commit | Roll back the event and state together. Reopen and retry the same event once. |
| Database reopens after a successful commit | Restore the committed revision; duplicate retry remains a no-op. |
| State checksum differs | Stop with `journal_state_checksum`; investigate the preserved database. Never invent a repaired balance. |

Use SQLite's transaction boundary as the commit point. A hash detects content changes; it is **not** a digital signature, authorization system or proof that source data are authentic. Local database durability settings, backups, concurrent service behavior, access control, network partitions and broker acknowledgments require further work before any production use. The injected failure verifies transaction rollback, not physical power-loss survival.

## Recorded acceptance evidence

`outputs/transition_lab/evidence.json` contains the original hypothetical snapshot, every budget plan, the independent assertions, eight blocked fault cases with clean retests, the six operating records and source hashes. The saved run is inspectable without opening the temporary database. The tests additionally cover stale revisions, conflicting idempotency keys, future cash availability, fee/tax/cash corruption, missing account plans, infeasible restrictions, no loss-credit assumptions, and an independently hand-derived cash/tax fixture.
