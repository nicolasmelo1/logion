<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Legal work and corporate structure

Split out of `next-steps.md` on 2026-08-17.

Exit condition: every trigger row in the sequencing table has its named work
done (policy published, DPA signed, escrow reviewed, licences documented) or
formally parked with counsel's reasoning recorded here, and the entity
recommendation below is either executed (entity formed) or re-decided in
writing.

> **This is a checklist for instructing counsel and an accountant. It is not
> legal or tax advice, and none of it has been reviewed by a lawyer yet.**
> Every fact below was gathered from public sources on 2026-08-17 and should be
> confirmed with a professional before acting.

## The sequencing rule

Doing "all the legal work" before shipping is the most comfortable way not to
ship. Each item below is tied to the step that first creates the exposure, per
[`next-steps.md`](next-steps.md).

| Trigger | Work | Why it binds there |
| --- | --- | --- |
| Before the **first public measurement** (step 6) | Publication policy: methodology disclosure, reproducibility, stated limits, no causal claims, documented right of reply, and a **published takedown policy** | First time Logion makes a public factual claim about a third party's commercial product. Nearest-term exposure in the whole plan, and it is not about payments. |
| Before **15.11.1** reaches any external publisher (step 2) | Data-protection basis, DPA, and consent copy covering **both** roles below | The publisher becomes controller for their users' data and cannot ship an instrumented projection without paper. |
| Before the first **externally funded bounty** (Loop C, 0.3) | Escrow / fund-holding review, contributor agreement, IP assignment for bounty output | Money held between funder and contributor is where Stripe Connect stops covering the structure. |
| Before broader indexing/mirroring | Per-artifact licence compatibility, attribution, takedown and claim process | Already ethically settled in the workspace README; not yet legally documented. |
| **Now, in parallel** | Entity formation | Long lead time; everything above needs a counterparty that is not a personal CNPJ. |

Operational detail of the publication policy lives in
[`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md).

## Data protection — the part that is actually dangerous

### Controller/processor split, decided explicitly

The observability product contains two distinct processings that do not share a
legal basis:

1. **Publisher's own dashboard.** Logion processes on the publisher's
   instructions. Logion is a **processor**; the publisher is the **controller**.
   Standard DPA.
2. **Cross-publisher cohort benchmarks.** The moment Logion aggregates across
   publishers to produce comparison statistics, it is no longer acting on any
   single publisher's instructions. Under GDPR a processor acting outside
   controller instructions **becomes a controller for that processing, with full
   controller liability** — and benchmarking client data is the named example.

Consequences that must reach the implementation, not only the paperwork:

- **Two legal bases, two disclosures.** The consent copy specified in 15.11.1
  covers "the publisher receives usage metadata". It does **not** cover "this
  joins an aggregate other companies can see". That is a gap in the consent
  text, and mismatch between disclosed practice and actual back-end flow is
  precisely the current enforcement focus.
- LGPD applies alongside GDPR.
- The app publisher remains primary controller for everything inside a
  third-party library they ship — which is exactly why they will demand a DPA
  before bundling Logion's reporter, and why the DPA is a **sales asset** rather
  than overhead. No company installs a telemetry companion without one.

### Engineering controls are compliance evidence

Describe them as such. Regulators are actively looking for analytics SDKs firing
before the consent interface; Logion's gate asserts the opposite and can prove
it:

- `files.consent_recorded_before_observation`
- `api.private_payload_absent`
- `api.disabled_use_zero_receipts`
- `api.install_not_counted_as_use`
- privacy-canary tests for prompt, file, path, tool arguments/results, secrets,
  identity
- schema-level rejection of undeclared fields, not policy-level filtering
- `DO_NOT_TRACK` / `LOGION_DO_NOT_TRACK` forcing `off`, with no inverse signal
  ever read
- denial leaving the resource operational with byte-identical no-telemetry state

## Publication liability

The exposure created by measuring artifacts nobody asked to be measured. It is
the direct cost of the garden-without-walls position: a walled garden rates
tenants who accepted its terms; Logion rates strangers who agreed to nothing and
are sometimes commercial competitors of one another.

Mitigations, all cheap, all in the playbook:

- publish the methodology and the selection policy;
- results must reproduce before publication;
- state limits and what the contract does not test;
- never assert causation;
- **right of reply before publishing**, by email, with a stated window;
- correct errors loudly and fast;
- publish a takedown policy *before* the first request arrives.

The standing rule — *no public claim can be stronger than its underlying
evidence and local authority policy* — is a legal control, not only an
epistemic one.

Escalate to counsel rather than improvising when a request alleges defamation,
asserts a licence or terms breach, or arrives from a lawyer.

Separately: evaluation executes third-party code. Sandbox isolation and the
terms under which someone else's artifact is run need their own review.

## Payments — the least dangerous part

The existing structuring in `logion/packages/landing/landing/content/legal/credits.md`
is already correct in its essentials: credits as a non-cash, non-transferable,
non-redeemable prepaid usage right, explicitly not money, stored value, or a
security, with creator/contributor payouts separated from buyer credit
redemption.

Stripe Connect shifts money-transmission licensing to Stripe because the
platform never takes possession of funds.

**The open question is narrower than "do we need a money transmitter licence":**
whether holding a funded bounty between funder and contributor constitutes
escrow, since Connect is explicitly **not** escrow in the legal sense. That is
the specific question to put to counsel, and it binds at Loop C, not at 0.2.

Existing legal content that needs a truth pass alongside the landing:
`terms.md`, `privacy.md`, `credits.md`, `referrals.md` — all dated 2026-06-26
and all written for the marketplace framing.

## Entity

Current state: transactions run through a personal Brazilian ME,
**Nicolas Leal de Melo LTDA**.

### The recommendation

**Form a US entity — but not for tax reasons.** The tax argument that appears in
every English-language guide does not survive contact with Brazilian CFC rules.

Why to do it anyway:

1. International payouts to contributors are dramatically simpler from a US
   entity.
2. **No company will sign a DPA with, or send its users' telemetry to, a
   personal Brazilian ME.** Counterparty credibility is the real reason.
3. It separates Logion's liability from personal assets — material given the
   publication and data-protection exposure above.
4. It is a prerequisite for ever raising, and converting later is cheap.

### LLC vs C-Corp

- Stripe Atlas defaults to a Delaware C-Corp.
- **Choose C-Corp only if raising US venture capital** within roughly 12–24
  months.
- Otherwise **LLC**: cheaper, simpler compliance, and convertible to a C-Corp
  later — usually tax-free, in 2–4 weeks, via a single statutory filing.

Given no raise planned in that window: **LLC now, convertible later.**

### The Brazilian side, which dominates the arithmetic

Under **Lei 14.754/2023**:

- A Brazilian tax resident controlling **more than 50%** of a foreign entity pays
  a flat **15% on the offshore company's annual net profit every 31 December —
  even if nothing is distributed.**
- Brazil **does not recognise US check-the-box elections**. An LLC with legal
  personality under US law, controlled by a Brazilian resident, is typically
  treated as a separate corporation subject to CFC taxation.
- Therefore the headline LLC advantage — pass-through, potentially US$0 US
  federal tax — **largely evaporates for a Brazilian-resident owner**, because
  Brazil taxes it as a company regardless.
- **CBE** filing with BACEN is required if foreign assets exceed US$1,000,000 on
  31 December, with fines reported up to R$250,000. Not yet applicable; note it.

**Action:** hire a Brazilian accountant who knows Lei 14.754 *alongside* the
formation service. Stripe Atlas will not mention CFC, and the dominant cost of
the structure sits on the Brazilian side, not the American one.

### Timing

Start now, in parallel with code — formation takes weeks and is the counterparty
for every other item in this file. The hard trigger is the first time Logion
holds third-party money destined for a contributor (Loop C). Do not let it
become the reason 0.2 slips.

## The standing warning

None of this makes Logion a company. It makes Logion *look* like one. What makes
it a company is the first public measurement landing and someone funding a
bounty because of it.

Run these items **in parallel** with steps 1–6, never before them. The failure
mode is an immaculate LLC with reviewed DPAs and a beautiful landing page and no
revenue — the most expensive and most convincing way to keep not shipping.

## Sources consulted (2026-08-17)

Public sources only, none authoritative for a decision:

- Stripe Atlas LLC vs C-Corp guidance; Stripe Connect and money-transmission
  material.
- Brazilian CFC / Lei 14.754/2023 commentary and CBE/BACEN filing guidance.
- GDPR controller-vs-processor liability material, including processors acting
  outside instructions and 2026 enforcement patterns around SDK consent timing.
