# reqlint

A small, dependency-free linter for ambiguous and untestable language in requirements text — based on the [INCOSE Guide for Writing Requirements](https://www.incose.org/) and common EARS-syntax conventions.

Flags things like:
- Ambiguous terms ("appropriate", "user-friendly", "fast") that can't be tested objectively
- Weak modal verbs ("should", "may", "could") where a binding requirement needs "shall"
- Relative performance claims ("fast", "quickly") with no attached unit or threshold
- Vague pronoun leads ("It shall...", "This shall...") that hide the actual subject

## Usage

```bash
python3 reqlint.py requirements.txt
python3 reqlint.py requirements.txt --json
python3 reqlint.py requirements.txt --fail-on high   # non-zero exit for CI gating
```

One requirement per line in the input file.

## Why

Catching ambiguous requirement language early is cheap; catching it after the spec ships to a supplier or into a build is not. The cost of removing a defect rises the later it is found — see Boehm & Basili, ["Software Defect Reduction Top 10 List"](https://doi.org/10.1109/2.962984), *IEEE Computer* 34(1), 2001, which reports the effect while noting the ratio varies widely with system size and criticality. `reqlint` catches the "obviously untestable" tier of that problem — vague/weak language — for free and at commit time.

It's a companion to a longer piece on requirements quality and hybrid contradiction detection: https://wyzer.it/blog/contradiction-detection-hybrid-approaches

## Scope

This is a rule-based lint for *language quality* — ambiguous wording, weak modals, missing units. It does not do semantic contradiction detection, duplicate detection, or cross-document analysis; that's a substantially harder problem (see the blog post above for why naive text-similarity approaches fall short there).

## License

MIT
