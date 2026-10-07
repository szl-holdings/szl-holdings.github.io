# Four SAMPLE receipt verification cases

This original runner exercises the GovernedAction v1 contract in canonical
`szl-holdings/szl-receipt` at revision
`1467fcbd1ff57b955d588c73e64a541ebc16770f`. It performs no provider operations,
model calls, deployment or real action. Its inputs are explicitly SAMPLE.

The complete case returns PASS. The changed payload, missing witness and unsigned
cases return INCOMPLETE. Exit 0 means the harness observed all expected outcomes,
including the three refusals. An INCOMPLETE case remains INCOMPLETE.

## Run in PowerShell

Install Git and CPython 3.11 or 3.12 first. Review `replay.py`, `sample-input.json`,
`source-lock.json` and `requirements.lock`. From the extracted bundle directory:

```powershell
git -c core.autocrlf=false clone --no-checkout https://github.com/szl-holdings/szl-receipt.git receipt-source
git -C receipt-source -c core.autocrlf=false checkout --detach 1467fcbd1ff57b955d588c73e64a541ebc16770f
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python.exe -I replay.py --source-dir receipt-source --output my-run.json
```

Use `py -3.12` for the environment creation if Python 3.12 is installed. The lock
contains approved unyanked wheel hashes from official PyPI metadata for several
platforms. If your platform has no matching wheel, installation stops. Do not
remove the hashes or permit an unreviewed source build to clear that failure.

## Run on Linux or macOS

```sh
git -c core.autocrlf=false clone --no-checkout https://github.com/szl-holdings/szl-receipt.git receipt-source
git -C receipt-source -c core.autocrlf=false checkout --detach 1467fcbd1ff57b955d588c73e64a541ebc16770f
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/bin/python -I replay.py --source-dir receipt-source --output my-run.json
```

## Interpret the report

- Inputs are **SAMPLE**. Actor authentication, subject digests, policy evidence,
  independent-witness flags and internal VERIFIED tokens are fixture assertions.
- Key generation, ECDSA signing and verification are actually executed. A fresh
  key pair exists only in process memory. No key, signature bytes or secret is
  persisted by this runner. The report retains non-secret digests and outcomes.
- A valid signature is checked separately from admission completeness. The
  signed record missing its witness keeps a valid signature and stays INCOMPLETE.
- Freshness uses the fixed SAMPLE assessment time, not today's wall clock. No
  current provider state or real independent witness is established.
- Key trust is local SAMPLE only. Outside replay is **NOT RUN**; real-world
  authorization and runtime state are **UNKNOWN**; production remains **BLOCKED**.
- Source and fixture hashes and expected outcomes are reproducible. Ephemeral
  keys and signed envelope hashes vary per execution. Compare case identifiers,
  statuses, required reasons, signature validity, source and fixture bindings.
- Dependency versions are checked at run time. Hash-checked installation verifies
  the downloaded wheels; the replay does not revalidate installed dependency
  bytes. Their installed integrity is recorded as **UNKNOWN**.
- PyPI `szl-receipt-dsse==0.3.3` is a separate distribution. Its equivalence to the
  pinned source revision remains **UNKNOWN**; this runner imports reviewed source.

Source and input integrity checks stop before canonical imports. Run Python with
`-I` to exclude ambient import paths. The runner also refuses unexpected Python
modules and compiled artifacts in the source import root. Use a clean checkout
with LF bytes; modifying the locked source causes rejection. This is not a
sandbox for arbitrary code or a substitute for reviewing the pinned source.

## Provenance and prior art

`bundle-manifest.json` hashes the published files. It is a repository-declared
integrity record, not a signature or independent authority. `measured-run.json`
records one actual local replay and its explicit limits.

The runner is Apache-2.0. Canonical source is fetched separately with its own
LICENSE and NOTICE retained. Maintained dependencies implement cryptographic
operations and statement validation; this bundle adds no cryptographic primitive.

- Canonical source: https://github.com/szl-holdings/szl-receipt/tree/1467fcbd1ff57b955d588c73e64a541ebc16770f
- DSSE protocol: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
- in-toto attestation: https://github.com/in-toto/attestation
- pyca/cryptography: https://cryptography.io/en/latest/

Independent outside replay, model inference, energy measurement and provider
mutation were **NOT RUN**. The examples grant no tool execution or production
authorization.
