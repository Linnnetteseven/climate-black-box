# Integrity on CKB: the Evidence Ledger and the Evidence Gate

Climate Black Box commits its evidence to Nervos CKB so that a finding can't be revised after the fact, not even by us. This page explains exactly what is committed, what the chain enforces, and what it doesn't prove.

## What gets committed
Each audit event (an observation, an alert, a resolution, an investigation, an intervention) is a **manifest**. It's built deterministically (numbers frozen as fixed-precision text; see `services/ckb/manifest.py`), canonicalised and hashed with sha256. Only the hash goes on chain. The manifest itself can reference material we have no business publishing.

## Evidence Ledger (type script)
One cell per project, identified by a Type ID. Its 48-byte data is the running state:

| Field | Meaning |
|---|---|
| `seq` | events recorded so far |
| `head` | `blake2b(head ‖ entry)` folded over every entry |
| `last_period` | latest observed month (YYYYMM) |
| `open_alerts` | alerts raised and not yet resolved |

Each append carries its events in the transaction's witness, one 37-byte entry per event: `kind ‖ period ‖ manifest_sha256`. The type script re-folds them itself and requires the new cell to match exactly. Rules enforced on chain:

- **Order:** only the recorder (the project's recorder wallet) can append, and the cell's lock and capacity can't change.
- **No rewrites:** history can't be pre-filled at creation, rewritten, reordered or skipped. Any change to the head is detected.
- **No forks or deletions:** a ledger can't split into two histories, and it can't be deleted.
- **Time only moves forward:** observations never go back in time.
- **Alerts are counted honestly:**
  - an alert must be about a month already observed;
  - an alert can't be dropped quietly;
  - nothing can be "resolved" that wasn't raised.

Because the entries live in witnesses, **anyone** can read the full history back from the chain and re-fold it with no access to our database (`services/ckb/ledger.mjs history`). Our verifier does that, then checks each record we hold sits at its exact position. The states it reports:

| State | Meaning |
|---|---|
| `verified` | the record matches its position, and the whole ledger re-folds to the on-chain head |
| `modified` | the record changed after it was recorded |
| `out_of_sequence` | the record is on the ledger, but in a different position |
| `not_anchored` | the record hasn't been appended yet |
| `pending` | an anchor was submitted but isn't confirmed yet |
| `chain_unavailable` | we couldn't reach CKB, which says nothing either way |

## Evidence Gate (lock script)
Donations are CadencePay subscriptions (`cadencepay` on npm, deployed and tested separately) whose recipient is a gate rather than the project's wallet. CadencePay is unchanged: it still pays exactly one amount per period. The gate's args are `ledger_type_hash ‖ project_lock_hash ‖ donor_lock_hash`, and it reads the project's ledger as a **cell dep**. Consensus only accepts live cell deps, and the ledger is unique, so the gate always sees the current evidence:

- **The project** can spend while `open_alerts == 0`.
- **The donor** can take a payment back while `open_alerts > 0`.
- **Nobody else:** a missing ledger, another project's ledger, or a stranger opens nothing.

## Deployments (CKB testnet, `data1`, immutable)
| Script | Code hash | Deploy tx |
|---|---|---|
| evidence-ledger | `0x3429e6ce625cf133dccd5b83218b97c14884f1e5031e077c6b289d7f533908e5` | `0x42eedf8a479ab1ee0a178c0c061700ce159f1356f2bcd33d2b9fa7beeb711cfa` |
| evidence-gate | `0x5b74aa07d17d7d0f53159548ab9ebf4a259f0db1df2130ba5db9b60f16dcfc3d` | `0x80267d1e6dd10cfff0c39cdbf071cda2f45cfb3ca43a7c41ec54902ad2dddabe` |
| CadencePay v3 | `0x7c271b62bc4b726f5997f3dbd221cfdbf31c944da19871dc1d8fc3bb75910419` | `0x8acdf7ed16e21ed29c3fc0c9f2067e8901e7ee8dce5a1b4c686e5c24c9eada8b` |

Source and 31 attack tests: `experiments/time-lock-script` in [ckbuilders](https://github.com/Linnnetteseven/ckbuilders) (`cargo test -p tests evidence`), including a test where the real CadencePay binary pays into a gate.

## Verified on testnet (`services/ckb/e2e-funding.mjs`)
Every step below ran on CKB testnet, in under six minutes:

- **Ledger:** created, then three observations recorded in one append.
- **Donation:** a donor subscribed via `cadencepay`, and the first payment went into the gate.
- **Clean evidence:** the project withdrew the payment.
- **Alert:** after an alert was recorded, a second donation arrived. **The project's withdrawal was refused by the gate script**, and the donor took the payment back.
- **Resolution:** the alert was resolved and both subscriptions were cancelled, with their balances refunded.
- **Read-back:** the history was read back and re-folded from the chain: 5 events, intact.

Ledger `type_id` `0x9fac11fdd3cc235c8becfbde42121c16664ebc8c475ad30d2827b5edcb9dd258`; per-step transactions are in the ckbuilders `notes/deployments.md`.

## What this does not prove
**Integrity is not truth.** The ledger proves records haven't changed and are in order. It doesn't prove a measurement was right, a sensor calibrated, or an interpretation correct. The gate acts on the ledger's alert count, and an alert means the satellite record diverged from the commitment, not that anyone did anything wrong. Resolving an alert is a recorded act: who resolved it and why are committed to the ledger like any other evidence.
