# Licensing

This research artifact uses layered licensing by artifact role and path. This file is the scope index; the standard license texts are included under LICENSES/.

## 1. Software — Apache License 2.0

The project-authored software, runtime, configuration templates, tests, and release tooling in the paths below are licensed under Apache-2.0. The full standard text is LICENSES/Apache-2.0.txt.

## 2. UGS-SYNTH benchmark — CC BY 4.0

The UGS-SYNTH-D01 public benchmark definition and benchmark-specific non-code material under cases/ugs_synth_d01/public/** are licensed under Creative Commons Attribution 4.0 International (CC BY 4.0). The full standard legal code is LICENSES/CC-BY-4.0.txt.

## 3. Authored documentation — CC BY 4.0

Project-authored documentation and release governance material in docs/** and the package-level documentation and metadata listed below are licensed under CC BY 4.0. This includes README.md, BENCHMARK_PROVENANCE.md, CITATION.cff, RELEASE_CONTENTS.md, REPRODUCIBILITY.md, SECURITY_AND_PRIVACY.md, KNOWN_ISSUES.md, AI_GENERATED_CONTENT.md, AI_CONTENT_INVENTORY.csv, PROVIDER_TERMS_REVIEW.md, SOURCE_PROVENANCE.json, RELEASE_MANIFEST.json, RELEASE_VERSION, LICENSE.md, ATTRIBUTION.md, NOTICE.md, and THIRD_PARTY_NOTICES.md, plus the repository-level release report at ../RELEASE_READINESS_REPORT.md, to the extent applicable rights are held by the project creator.

## 4. Frozen experimental evidence

The materials in evidence/** and the related frozen experiment records and derived analysis listed below are made available under CC BY 4.0, to the extent applicable rights exist and are held by the repository owner.

To the extent that the repository owner holds applicable rights in the frozen experimental evidence, those rights are made available under CC BY 4.0.

This licensing statement does not determine the copyrightability or authorship of individual AI-generated outputs and does not create rights where none exist. It does not override third-party rights.

The evidence contains AI-generated or AI-assisted materials produced during the reported experiments. Licensing these artifacts does not imply engineering certification, professional validation, regulatory compliance, or endorsement of their contents. The evaluator category confirmed_violation is a protocol label, not an independently certified engineering violation. See AI_GENERATED_CONTENT.md for roles, classifications, and interpretation limits.

## 5. Path-level scope

| Path or artifact class | License |
|---|---|
| src/**, scripts/**, docker/**, tests/** | Apache-2.0 |
| analysis/scripts/** | Apache-2.0; deterministic release tooling |
| experiments/runtime_variants/** | Apache-2.0; frozen runtime source variants |
| .env.example, .gitattributes, .gitignore, pyproject.toml, requirements-test.txt, uv.lock | Apache-2.0; project software/configuration files |
| cases/ugs_synth_d01/public/** | CC BY 4.0; UGS-SYNTH-D01 benchmark |
| docs/** and authored package-level documentation/metadata listed in section 3 | CC BY 4.0 |
| ../RELEASE_READINESS_REPORT.md | CC BY 4.0; repository-level release governance documentation |
| evidence/** | CC BY 4.0, to the extent applicable rights exist |
| experiments/configurations/**, experiments/manifests/**, experiments/summaries/** | CC BY 4.0, to the extent applicable rights exist; frozen experimental records |
| analysis/rebuilt_tables/** | CC BY 4.0, to the extent applicable rights exist; deterministic derived research records |
| LICENSES/Apache-2.0.txt, LICENSES/CC-BY-4.0.txt | Unmodified standard license texts; each remains governed by its own terms and is not relicensed by this artifact |

Where a path is covered by a specific row above, that artifact-role row controls over a general documentation description. External dependencies remain subject to their own licenses and are not relicensed here.

## 6. AI-generated content

AI-generated Worker, Reviewer, and blind-evaluator outputs are experimental evidence, not certified engineering designs, licensed professional review, or formal ground truth. See AI_GENERATED_CONTENT.md and AI_CONTENT_INVENTORY.csv. Their inclusion under the evidence scope above is only to the extent that applicable rights exist and are held by the repository owner.

## 7. Third-party material, references, and attribution

No project license is granted for third-party material. Bibliographic references identify external methods or publications. The referenced third-party publications themselves are not included in, and are not relicensed by, this artifact. Provider, product, service, and other trademarks remain with their respective owners. See THIRD_PARTY_NOTICES.md and ATTRIBUTION.md.

## 8. Research scope

This artifact is a research benchmark and experimental record. It is not a production engineering package and does not establish regulatory compliance or fitness for safety-critical deployment. UGS_FORMAL_STATE remains NOT READY.
