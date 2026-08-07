# Semantic Memory Exit v1

This is the one small post-freeze exit experiment. It runs GBrain, Mem0 OSS,
and Hindsight sequentially over the synthetic corpus in
`datasets/followups/semantic-exit-v1/`.

Category A is the provider's documented/native export or enumeration surface.
Category B is a separately labelled copy of run-owned raw state where a
technically capable operator could copy it for disaster recovery. Category B
is never used as the primary portability result.

The runner records native population, deterministic retrieval observations,
semantic-property classifications, artifact hashes, destruction receipts,
same-system recovery, and ledgered model usage. It intentionally does not
implement a cross-provider conversion library. The default run is:

```powershell
$env:SOVBENCH_PROTOCOL_COST_APPROVED = "1"
$env:GBRAIN_BIN = "$env:USERPROFILE\.bun\install\global\node_modules\gbrain\src\cli.ts"
$env:BUN_BIN = "$env:USERPROFILE\.bun\bin\bun.exe"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:4713/v1"
python scripts/run_semantic_memory_exit.py
```

The experiment's generated state is under the ignored `runs/followups/`
directory. Private gold is loaded only by the runner's analysis process and is
never copied into provider state or sent to the reader gateway.
