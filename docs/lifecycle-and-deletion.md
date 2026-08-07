# Lifecycle and Deletion

## Events

The corpus replays `upsert` and `delete` (including do-not-store) events in a
single controlled batch: all non-delete events are ingested, then delete
events are applied through the provider's native delete API via the adapter
lifecycle mapping.

## Deletion attribution

For every provider, AMSB records:

1. native delete mechanism (product API)
2. adapter mapping from abstract delete event to that API
3. deleted-target retrieval under native/raw retrieval after deletion
4. any additional benchmark filtering contribution

Researched result: GBrain, Mem0, and Hindsight each removed deleted evidence
from bounded retrieval natively, with no benchmark post-filtering required.
Mem0's `delete` removes memories; GBrain removes pages; Hindsight removes
bank memories.

## Unsupported deletion

If a provider cannot delete (for example OptMem's append-only design), the
adapter raises `CapabilityNotSupported` and the manifest records
`deletion = unsupported`. It is never faked and never silently omitted.

## Verification

Deletion is verified by raw retrieval after the delete call, with state
hashes recorded before and after. The scorer never suppresses deleted
evidence; it counts exposure.
