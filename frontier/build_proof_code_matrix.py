"""Build an evidence-limited, revision-pinned inventory of szl-formulas.

This parses public source as text/AST. It does not import executable formula code,
run Lean, infer an F-number mapping, or claim a Hub publication.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import subprocess
from pathlib import Path


FORMULA_SHA = "4eb866bf78da5fa639b8f23d213756d80ba38534"
LEAN_SHA = "3b0b589ea332fe962afff13328d9675b525e1819"
LOCKED_IDS = {"F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"}
SOURCE_PATH = "torch-ext/szl_formulas/_formulas.py"

# These are source-level guard/claim observations, not formal proof assertions.
NOTES = {
    "lambda_aggregate": ("Finite axes in [0,1]; positive weights summing to 1 within 1e-12; nonempty.", "Related Lean Λ and conditional separability theorem; Python float refinement is unverified. Unconditional A1-A5 uniqueness is refuted in Lean.", "tests/test_formulas.py; tests/test_lambda_v1_conformance.py"),
    "lambda_homogeneous": ("c >= 0 and c*x remains in the valid [0,1] domain.", "Registry says AXIOM(A2); this callable checks one approximate instance, not a universal theorem.", "tests/test_lambda_v1_conformance.py"),
    "lambda_bounded": ("Nonempty valid axis list in [0,1].", "Returns a tolerance-based Boolean for the supplied vector; Lean-to-float refinement is unverified.", "tests/test_formulas.py; tests/test_lambda_v1_conformance.py"),
    "pac_bayes_mcallester": ("n > 0; 0 < delta < 1; KL >= 0. Empirical risk range is not checked.", "Computes a bound expression; PAC-Bayes proof obligation is marked SORRY.", "NO_DIRECT_ASSERTION_FOUND"),
    "bekenstein_cascade": ("R and E >= 0; physical units are not checked.", "Lean locked F19 is Nat addition monotonicity, not this entropy expression.", "NO_DIRECT_ASSERTION_FOUND"),
    "reidemeister_invariant": ("Braid word is not validated; any move other than R1/R2 falls through the R3 branch.", "Axiom-gated source label; knot equivalence is not established by this string rewrite.", "NO_DIRECT_ASSERTION_FOUND"),
    "khipu_merkle_root": ("Receipt decision_id and int-convertible value; hashes sorted leaves and includes total.", "Lean locked F4/F22 concern a Nat DAG/backward edges and append-only sequence, not this byte hash function.", "NO_DIRECT_ASSERTION_FOUND"),
    "dsse_envelope": ("Payload bytes and signer label; signature field is a SHA-256 PLACEHOLDER.", "Envelope construction does not create or verify a cryptographic signature.", "NO_DIRECT_ASSERTION_FOUND"),
    "gleason_quantum_lambda": ("Square numeric matrix; density-matrix PSD, Hermiticity and trace-one are not checked.", "Returns trace(rho^2); claimed purity range is conditional on a valid density matrix.", "NO_DIRECT_ASSERTION_FOUND"),
    "hoeffding_tail": ("n > 0; t >= 0; independence/boundedness assumptions are not checked.", "Computes a capped expression; no sampled probability or statistical coverage check.", "tests/test_formulas.py"),
    "pinsker_kl_bound": ("Equal lengths and approximate unit sums; nonnegative entries are not checked.", "Returns 2*TV^2, not KL; Lean source label remains AXIOM(pinsker).", "NO_DIRECT_ASSERTION_FOUND"),
    "fisher_rao_distance": ("Equal lengths and approximate unit sums; negative entries are clamped inside sqrt.", "Closed-form label is a reported obligation; simplex membership is not fully enforced.", "NO_DIRECT_ASSERTION_FOUND"),
    "bohr_complementarity_floor": ("Nonnegative sigma_A and sigma_B.", "Checks a numeric threshold with EPS; no operator/commutator hypotheses are represented.", "NO_DIRECT_ASSERTION_FOUND"),
    "kochen_specker_18vector_witness": ("Rows int-convertible; every row sums to one and context count is odd.", "No 18-vector construction or orthogonality validation; status is AXIOM(KS-18 scaffold).", "NO_DIRECT_ASSERTION_FOUND"),
    "two_witness_ks18_soundness": ("Two Boolean-like inputs.", "Returns w1 and w2; independence and soundness are not checked; status is SORRY.", "NO_DIRECT_ASSERTION_FOUND"),
    "shor_codeword_distance": ("Iterable of bit-like rows; converts values to int and uses bit & 1.", "Minimum supplied nonzero row weight equals code distance only if a suitable full codeword set is supplied.", "NO_DIRECT_ASSERTION_FOUND"),
    "css_ingress_verify": ("Envelope payload hex and root bytes; compares only first four digest bytes.", "Does not verify DSSE signature or complete transparency-root binding.", "NO_DIRECT_ASSERTION_FOUND"),
    "kitaev_surface_correct": ("Syndrome values int-convertible.", "Returns parity bits; no surface-code syndrome decoding proof; status AXIOM.", "NO_DIRECT_ASSERTION_FOUND"),
    "reed_solomon_singleton": ("Integers satisfying 0 < k <= n.", "Returns n-k+1; locked F18 proves RS(10,6) parity arithmetic, not this general code-bound implementation.", "tests/test_formulas.py"),
    "madhava_series": ("terms > 0; |x| <= 1.", "Returns a finite partial sum, not exact atan; source has a numerical pi approximation test.", "tests/test_formulas.py"),
    "schur_concave_lambda_two_axis": ("Two valid axes in [0,1].", "Checks one two-axis inequality with EPS; n-axis statement remains AXIOM in source label.", "tests/test_lambda_v1_conformance.py"),
}

RELATED = {
    "lambda_aggregate": ("CONDITIONAL_RELATED_FORMALIZATION", "Lutar/Round13/LambdaSeparable.lean#L85; Lutar/Round13/Lambda_Uniqueness.lean#L188"),
    "lambda_homogeneous": ("NAMED_LEAN_PROPERTY_NO_REFINEMENT", "Lutar/Axioms.lean#L93"),
    "lambda_bounded": ("NAMED_LEAN_PROPERTY_NO_REFINEMENT", "Lutar/Axioms.lean#L111"),
    "bekenstein_cascade": ("NON_EQUIVALENT_LOCKED_TOPIC", "claims/locked-formulas.v1.json#F19"),
    "khipu_merkle_root": ("NON_EQUIVALENT_LOCKED_TOPIC", "claims/locked-formulas.v1.json#F4-F22"),
    "reed_solomon_singleton": ("NON_EQUIVALENT_LOCKED_TOPIC", "claims/locked-formulas.v1.json#F18"),
}


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def require_pinned_bytes(tree: Path, sha: str, relative_path: str) -> None:
    """Reject input edits; Git handles checkout CRLF normalization on Windows."""
    if not (tree / relative_path).is_file():
        raise SystemExit(f"missing pinned input: {relative_path}")
    result = subprocess.run(
        ["git", "-C", str(tree), "diff", "--quiet", sha, "--", relative_path],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"working-tree content differs from pinned Git blob: {relative_path}")


def literal_dict(module: ast.Module, name: str) -> dict:
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            if name == "REGISTRY":
                assert isinstance(node.value, ast.Dict)
                return {ast.literal_eval(k): v.id for k, v in zip(node.value.keys, node.value.values)}
            return ast.literal_eval(node.value)
    raise ValueError(f"missing {name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    default_cache = Path(__file__).resolve().parent.parent / "_formula_source_20261002"
    ap.add_argument("--formula-tree", type=Path, default=default_cache / "szl-formulas")
    ap.add_argument("--lean-tree", type=Path, default=default_cache / "lutar-lean")
    args = ap.parse_args()
    if git_head(args.formula_tree) != FORMULA_SHA or git_head(args.lean_tree) != LEAN_SHA:
        raise SystemExit("source revision mismatch; refuse to rebuild matrix")
    for relative_path in (SOURCE_PATH, "atlas/formula-atlas.v1.json"):
        require_pinned_bytes(args.formula_tree, FORMULA_SHA, relative_path)
    for relative_path in (
        "claims/locked-formulas.v1.json",
        "Lutar/Round13/LambdaSeparable.lean",
        "Lutar/Round13/Lambda_Uniqueness.lean",
    ):
        require_pinned_bytes(args.lean_tree, LEAN_SHA, relative_path)

    source = args.formula_tree / SOURCE_PATH
    module = ast.parse(source.read_text(encoding="utf-8"))
    registry = literal_dict(module, "REGISTRY")
    statuses = literal_dict(module, "PROOF_STATUS")
    functions = {n.name: n for n in module.body if isinstance(n, ast.FunctionDef)}
    atlas = json.loads((args.formula_tree / "atlas/formula-atlas.v1.json").read_text(encoding="utf-8"))
    claims = json.loads((args.lean_tree / "claims/locked-formulas.v1.json").read_text(encoding="utf-8"))
    assert len(registry) == 21 and set(registry) == set(statuses) == set(NOTES)
    assert all(name == symbol and name in functions for name, symbol in registry.items())
    assert {x["claim_id"] for x in claims["claims"]} == LOCKED_IDS
    assert set(atlas["authority"]["locked_proven_ids"]) == LOCKED_IDS
    assert atlas["authority"]["f_number_to_executable_registry_mapping"] == "UNKNOWN_NOT_INFERRED"
    assert {x["name"]: x["proof_status"] for x in atlas["executable_formulas"]} == statuses

    base = Path(__file__).resolve().parent
    rows = []
    for ordinal, name in enumerate(registry, 1):
        fn = functions[name]
        relation, lean_fragment = RELATED.get(name, ("NO_SPECIFIC_FORMAL_LINK_IDENTIFIED", ""))
        assumptions, limit, test_ref = NOTES[name]
        lean_url = (f"https://github.com/szl-holdings/lutar-lean/blob/{LEAN_SHA}/{lean_fragment}"
                    if lean_fragment and not lean_fragment.startswith("claims/") else "")
        rows.append({
            "ordinal": ordinal,
            "callable": name,
            "code_revision": FORMULA_SHA,
            "code_path": SOURCE_PATH,
            "code_line": fn.lineno,
            "code_url": f"https://github.com/szl-holdings/szl-formulas/blob/{FORMULA_SHA}/{SOURCE_PATH}#L{fn.lineno}",
            "source_statement": ast.get_docstring(fn).splitlines()[0],
            "source_reported_proof_status": statuses[name],
            "input_conditions_observed": assumptions,
            "locked_f_id_verified": "",
            "proof_to_code_mapping": "UNVERIFIED",
            "related_formal_status": relation,
            "related_lean_url": lean_url,
            "source_test_reference": test_ref,
            "scope_or_gap": limit,
        })
    reported_counts = {
        label: sum(row["source_reported_proof_status"].startswith(label) for row in rows)
        for label in ("PROVEN", "AXIOM", "SORRY")
    }
    assert reported_counts == {"PROVEN": 12, "AXIOM": 7, "SORRY": 2}
    csv_path = base / "proof-to-code-matrix.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    md = [
        "# Proof-to-code inventory: 21 callable formulas",
        "",
        f"Source: [`szl-formulas@{FORMULA_SHA}`](https://github.com/szl-holdings/szl-formulas/tree/{FORMULA_SHA}) "
        f"and [`lutar-lean@{LEAN_SHA}`](https://github.com/szl-holdings/lutar-lean/tree/{LEAN_SHA}).",
        "",
        "**Result:** 21/21 Python registry callables identified; 0/21 have an authoritative, checked mapping "
        "to one of the eight locked F-number theorems. `UNVERIFIED` means no proof-to-implementation "
        "refinement was established; it does not mean the formula is false. The source's "
        "`PROOF_STATUS` strings are copied verbatim, not promoted to verified Lean claims.",
        "The 21 source labels begin with 12 `PROVEN`, 7 `AXIOM`, and 2 `SORRY`; these are "
        "obligation labels in the source catalog, not 12 checked Python implementations.",
        "",
        "The Lean locked set is `{F1,F4,F7,F11,F12,F18,F19,F22}`. Its "
        "[machine-readable claim manifest](https://github.com/szl-holdings/lutar-lean/blob/" + LEAN_SHA + "/claims/locked-formulas.v1.json) "
        "states narrower propositions and explicitly separates the genome/catalog labels from the compiled locked surface. "
        "The source [formula atlas](https://github.com/szl-holdings/szl-formulas/blob/" + FORMULA_SHA + "/atlas/formula-atlas.v1.json) "
        "itself records `f_number_to_executable_registry_mapping: UNKNOWN_NOT_INFERRED`.",
        "",
        "| # | Callable and source line | Source statement (first line) | Reported status | Formal relationship |",
        "|---:|---|---|---|---|",
    ]
    for row in rows:
        statement = row["source_statement"].replace("|", "\\|").replace("\n", " ")
        status = row["source_reported_proof_status"].replace("|", "\\|")
        md.append(f"| {row['ordinal']} | [`{row['callable']}`]({row['code_url']}) | {statement} | `{status}` | `{row['related_formal_status']}`; mapping `UNVERIFIED` |")
    md += [
        "",
        "## Boundaries that matter for the showcase",
        "",
        "- **Λ:** `lambda_aggregate` computes a floating-point weighted geometric mean on a restricted "
        "[0,1] contract. Lean's `lambda_unique_of_separable` is conditional on A1–A5 plus separability, "
        "multiplicative/monotone slices and normalization. `maxAgg_ne_Lambda` proves bare A1–A5 "
        "do not force Λ. Neither result certifies this Python implementation. "
        "[Conditional theorem](https://github.com/szl-holdings/lutar-lean/blob/" + LEAN_SHA + "/Lutar/Round13/LambdaSeparable.lean#L85) · "
        "[counterexample](https://github.com/szl-holdings/lutar-lean/blob/" + LEAN_SHA + "/Lutar/Round13/Lambda_Uniqueness.lean#L188).",
        "- **Similar names are not a map:** Lean F18 proves RS(10,6) parity arithmetic; "
        "`reed_solomon_singleton` returns `n-k+1`. Lean F19 is Nat addition monotonicity; "
        "`bekenstein_cascade` computes a dimensional entropy expression. Lean F4/F22 do not prove "
        "`khipu_merkle_root` hash behavior.",
        "- **Implementation guards are narrower than mathematical hypotheses:** the matrix CSV records "
        "each callable's input conditions and the visible gap. For example, `gleason_quantum_lambda` "
        "does not validate a density matrix, `pinsker_kl_bound` does not compute KL, "
        "`css_ingress_verify` compares four digest bytes, and `dsse_envelope` uses a placeholder signature.",
        "- **Tests and proof:** source tests exercise several numeric vectors and rejection paths, "
        "but test success is not a Lean-to-Python refinement proof. `NO_DIRECT_ASSERTION_FOUND` in the CSV "
        "means this inspection did not find a direct assertion in the primary source tests.",
        "",
        "## Next implementation gate",
        "",
        "For a demonstrable mapping, add a reviewed contract for each chosen callable: a formal theorem "
        "with its exact hypotheses, a finite/float representation relation, a pinned test vector and "
        "error bound, and a CI check that binds the source commit to the theorem and vector. "
        "Start with `lambda_aggregate`/`lambda_bounded`; keep F18 and F19 unmapped unless the "
        "Python semantics are actually refined to their narrower Lean statements.",
        "",
        "## Verification method",
        "",
        "[The rebuild script](build_proof_code_matrix.py) parses the two public worktrees without importing their code. "
        "It refuses unexpected Git HEADs, checks the exact 21 registry symbols and source status strings "
        "against the checked-in atlas, checks the eight compiled claim IDs, and fails if the atlas "
        "starts asserting an F-number mapping. This pass did not run Lean, execute all 21 functions, "
        "or establish Hub mirror parity. Run it with `--formula-tree` and `--lean-tree` pointing to clean "
        "checkouts at the pinned SHAs above."
    ]
    (base / "PROOF_TO_CODE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "rows": len(rows), "reported_counts": reported_counts,
                      "verified_locked_mappings": 0,
                      "formula_sha": FORMULA_SHA, "lean_sha": LEAN_SHA}))


if __name__ == "__main__":
    main()
