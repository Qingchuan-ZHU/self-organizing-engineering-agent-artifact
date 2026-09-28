# Provider Terms Review

Review date: 2026-09-28. This is a bounded release-governance review of official provider materials relevant to the recorded experiment and release attribution. It does not identify the exact account or contract accepted for each historical call.

## Terms reviewed

| Provider | Official document | Published, updated, or effective date shown by provider | Relevance |
|---|---|---|---|
| DeepSeek | [Open Platform Terms of Service](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) | Released 2026-04-22; effective 2026-04-29 | API input rights, output rights, academic use, AI disclosure, DeepSeek marks |
| DeepSeek | [Terms of Use](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html) | Last update 2026-03-27 | Publication/dissemination verification and AI-generated disclosure |
| OpenAI | [Services Agreement](https://openai.com/policies/services-agreement/) | Updated 2025-12-01; effective 2026-01-01 | Conditional business/developer and API route; input/output rights, customer duties, publicity |
| OpenAI | [Terms of Use](https://openai.com/policies/row-terms-of-use/) | Published and effective 2026-01-01 | Conditional individual ChatGPT-account route; input/output rights and accuracy duties |
| OpenAI | [Service Terms](https://openai.com/policies/service-terms/) | Updated 2026-09-21 | Service-specific terms, including conditional API and enterprise output indemnity and Codex code-generation note |
| OpenAI | [Sharing & Publication Policy](https://openai.com/policies/sharing-publication-policy/) | Updated 2022-11-14 | API co-authored content disclosure and research publications |
| OpenAI | [Using Codex with your ChatGPT plan](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan) | Page showed updated five days before this review | Explains individual ChatGPT versus API/business/enterprise/education agreement paths |

## DeepSeek

The frozen Worker and Explicit-collaboration Reviewer configurations identify the DeepSeek Open Platform API, the deepseek-flash model, and the DeepSeek provider adapter. The OpenAI-compatible request format is a protocol detail and does not identify OpenAI as the model provider.

- **Output rights:** Section 4.2 says users retain rights, if any, in Inputs and DeepSeek assigns to the user rights, if any, in Outputs, subject to law and the terms.
- **Academic use:** Section 4.2 expressly lists academic research among permitted use cases, subject to applicable law and the terms.
- **Disclosure and accuracy:** Open Platform Terms section 8.1 requires clear disclosure to end users that service output is AI-generated, may contain errors or omissions, and is for reference only. It says outputs should not form the basis for further actions or omissions and places responsibility for decisions on the user. The Terms of Use section 3.1 separately requires users who publish or disseminate outputs to verify authenticity and accuracy and clearly identify the content as AI-generated.
- **Input rights:** Section 4.1 makes the user responsible for Inputs and Outputs and requires the user to have rights, licenses, and permissions needed for processing Inputs.
- **Accuracy and non-infringement:** Section 7.4 disclaims warranties that Outputs are accurate, current, reliable, or non-infringing.
- **Brand-use history:** Section 5.2 broadly prohibits use of marks and other brand identifiers related to the service, expressly including the name DeepSeek, without permission; section 5.3 bars implied partnership, endorsement, or misleading relationship claims. No express academic-attribution exception was identified in the reviewed text. The package uses the name only for factual, non-promotional provider identification. The release-governance decision for this staged artifact accepts that attribution and records the matter as closed and not a publication blocker; this does not imply endorsement or permission to use logos or co-branding. No logo, co-branding, endorsement, or partnership claim was identified in the package review.

**Assessment:** No general provider-term prohibition on academic use or publication of API outputs was identified; academic research is expressly listed. The terms finding remains in this governance record; the owner has accepted the package's factual attribution and it is not a publication blocker for this staged release. This decision is not a legal opinion or a claim of provider endorsement.

## OpenAI

Frozen evaluation metadata records Codex CLI and the requested/reported model value gpt-5.5. The controller invokes Codex CLI with a model argument. The frozen evidence does not preserve whether the execution used an individual ChatGPT account, an API credential, or an organization-managed ChatGPT workspace, and it does not contain a provider-side receipt confirming effective model identity. OpenAI's official Codex guidance says individual ChatGPT users are governed by individual Terms of Use, while API and business, enterprise, or education users are governed by the corresponding online services agreement. The governing route cannot be selected from the frozen process records.

- **Output rights:** The Services Agreement section 4.1 assigns to a business/developer customer rights, if any, OpenAI has in Output and states that the customer owns Output as between the parties to the extent permitted by law. The individual Terms of Use section 6 gives a similar ownership and assignment rule for individual services, subject to law. Neither term establishes universal copyrightability or third-party rights clearance.
- **Customer/user duties:** Under the Services Agreement section 4.3, the customer is responsible for having rights to provide Input, for Output use, and for evaluating accuracy and appropriateness. The individual Terms of Use sections 5 and 6 likewise assign responsibility for content and input permissions and require evaluating Output for accuracy and appropriateness, including human review as appropriate.
- **Misrepresentation and disclosure:** The individual Terms of Use prohibit representing Output as human-generated when it was not. The Sharing & Publication Policy asks publishers of first-party written content made in part with the OpenAI API to attribute it to the publisher, clearly disclose AI's role, describe the human and AI contributions accurately, and have a human take ultimate responsibility. That policy welcomes research publications related to the OpenAI API. The reviewed materials do not impose a specific per-file watermark requirement.
- **Service terms and code output:** The Service Terms updated 2026-09-21 say output from code-generation features, including Codex, may be subject to third-party licenses, including open-source licenses. This is relevant to the released code and reinforces that provider output assignment does not replace software and third-party license review. The same terms describe certain output IP indemnity for API and Enterprise customers, with exclusions including known or likely infringement, ignored relevant citation or safety features, modified/combined output, deficient Input rights, trademark claims, and Third Party Offering content. Applicability depends on the governing agreement and specific service. No API indemnity is treated as applicable here because the account route is absent from the frozen record.
- **Publicity and name-use history:** If the Services Agreement governs, section 10 requires express prior written permission for specified public statements about the relationship or agreement and for placing the other party's name or logo in websites, media, or marketing materials. The auth route is not in the frozen record, so applicability to factual attribution cannot be reconstructed. The release-governance decision accepts the package's factual, non-promotional tool attribution and records this historical uncertainty as closed and not a publication blocker for this staged release. The package review found no OpenAI logo, co-branding, endorsement, or partnership claim.

**Assessment:** The reviewed OpenAI materials do not identify a general prohibition on academic publication of the evaluation output; the API publication policy welcomes related research and describes disclosure and human-responsibility expectations. The exact agreement and any applicable publicity restriction cannot be determined from the frozen evidence. The historical uncertainty remains documented but is not a publication blocker under the release-governance decision. No API indemnity is assumed.

## Bounded content screening

A limited screen of 192 text files across published Worker submissions, Reviewer records and selected scripts, and blind-review outputs found no email patterns or common vendor-name matches, no long single-line quotation candidate at or above 25 words, and four URL matches. All four were W3C SVG namespace declarations inside generated diagrams. This screening does not establish the absence of all third-party material, personal data, or proprietary content and is not a similarity or legal review. No frozen evidence was edited to change output wording.

## Release labeling

Keep [AI_GENERATED_CONTENT.md](AI_GENERATED_CONTENT.md) and [AI_CONTENT_INVENTORY.csv](AI_CONTENT_INVENTORY.csv) with the package. They identify the model-produced evidence by group, distinguish deterministic tables from analyst-coded findings, and state that model reviews are not engineering ground truth. The frozen files remain unchanged.

## Scope and disclaimer

Provider terms can change and may vary by account, jurisdiction, and service. The exact Codex authentication route is not recorded in the frozen evidence. No provider contract or third-party content rights are certified by this review.

This review records the provider terms relevant to this research artifact as observed on the stated review date. It is a release-governance record, not legal advice or a guarantee regarding copyrightability, third-party rights, or future changes to provider terms.
