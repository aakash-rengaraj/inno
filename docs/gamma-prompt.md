# Gamma.ai prompt — paste everything below the line

---

Create a 10-slide presentation for a hackathon project submission. Follow the
slide structure exactly as given — one slide per numbered section, in order.

**Design direction:** This is a government enforcement tool, not a consumer
startup. Use a restrained, professional palette — deep slate blue as the
structural colour, a single muted red used *only* to mark severity, and a cool
grey background. Dense and tabular over airy and decorative. Use a monospaced or
tabular-figure font for all numbers so digits align in columns. No gradient
heroes, no icon-tile grids, no emoji. It should look like something a district
officer would file, not a pitch deck.

**Tone:** Precise and factual. Every figure below was produced by running the
system, so state numbers plainly without hype adjectives. Critically: the system
**flags patterns for investigation** — it never claims to have proven collusion.
Never use the words "proves", "caught", "cartel detected" or similar anywhere in
the deck.

---

## Slide 1 — Title Page

- **Track:** AIML-08
- **Problem Statement:** Price Manipulation Detection
- **Project name:** Price Review — Vellore District
- **Team name:** [TEAM NAME]
- **Members:** [NAME — REGISTRATION NUMBER] (repeat for each member)

Include the governing one-line thesis as a subtitle:
> Competitive prices track costs. Collusive prices track each other.

## Slide 2 — Problem Statement

Consumers and regulators cannot tell an expensive market from a manipulated one.
Prices rise for legitimate reasons — a poor harvest, fuel costs, seasonal
scarcity — and a regulator has no practical way to separate those from
coordinated pricing.

The enforcement problem is one of **attention, not authority**. A district supply
officer already has the power to inspect; what they lack is a defensible way to
choose *which* of hundreds of markets to inspect this week.

Concrete framing to feature prominently:
- Vellore district alone: **22 locations, 108 commodities, 216,732 price observations**
- No officer can review that manually
- Existing published rates (mandi reports, declared egg rates, gazetted auto
  fares) are *already public* — nobody is joining them to observed prices

## Slide 3 — Proposed Solution

A screening tool that compares what people are actually charged against what the
published rate says they should be charged, and turns the surviving gaps into
**printable case files** an officer can act on.

Four independent measures, each reconstructible by hand — **no black-box
classifier anywhere**, because every accusation must be explainable in a
document:

1. **Variance collapse** — independent sellers stop disagreeing on price
2. **Cost correlation** — prices track each other more closely than they track
   the published rate *(the headline measure)*
3. **Persistence** — a sustained gap above the expected range while named
   neighbouring markets stay inside it
4. **Quantisation** — fares cluster on round numbers and stop responding to distance

What makes it innovative — emphasise these three:
- **An evidence floor enforced in code.** A pattern resting on fewer than three
  independent localities is downgraded and withheld from the queue. It is an
  assertion, not a convention — simultaneously a data-quality, anti-gaming and
  defamation defence.
- **Locality generalisation.** Field reports are pseudonymised to a ~50m grid, so
  one person moving 100m could look like two independent witnesses. Reports
  within 150m quoting prices within 3% now collapse into one locality —
  corroboration cannot be manufactured. In the live data this collapsed **349
  reporting points into 119 localities**.
- **Named in-band peers on every flag.** Each finding lists the neighbouring
  markets that stayed inside their expected range over the same window — the
  direct answer to "maybe it was just a bad harvest".

## Slide 4 — Technical Approach

Include a left-to-right architecture flow diagram:

`Sources → Contracts → Generalise → Quantile band model → 4 detectors → Case files → Two web surfaces`

**Stack:** Python 3, pandas, LightGBM, FastAPI, SQLite, React, Vite, Recharts.

**The model:** three LightGBM quantile regressors (α = 0.1 / 0.5 / 0.9) fitted on
**102,134 rows** of mandi history, validated on a **time-based split** — never
random, because a random split leaks future prices into training.

Three deliberate design decisions worth calling out as engineering judgement:
- **The band is fitted in relative space** — `log(price ÷ regional peer level)`,
  not on price. Fitted on price directly the model extrapolates the training
  period's trend and marks every honest market as anomalous in a falling market.
- **Lags are of supply, never of a market's own price.** Any feature carrying a
  market's own price history lets a manipulated market justify itself —
  yesterday's collusive price predicts today's, the residual collapses, and the
  detectors go silent exactly where they should fire.
- **The peer level is a leave-one-out median, not a mean.** With a mean, one
  manipulated market lifts the expected band for its own honest neighbours and
  pushes *them* out of it.

**Two surfaces, separated by what they contain, not by hidden links:** the public
page and the enforcement console are separate builds. The public bundle carries
no flag IDs, no case narratives, no detector names, no thresholds — it cannot
name a flagged location even from page source.

## Slide 5 — Demo / Prototype

Show screenshots of: the inspection queue, a flag detail with its chart, and the
printed case file.

**Live on real government data:**
- **246,882 rows** of Agmarknet mandi prices, Vellore district, 2020–2026
- **597 days** of NECC declared egg rates
- **17 flags** in the inspection queue — **12 from real government data**
- **1 pattern withheld** for failing the evidence floor

Key features to list:
- Public page where any citizen reports a price they were charged
- A submitted report becomes tier-C evidence and re-runs detection in ~6 seconds
- Enforcement console: queue, flag evidence, action board, printable A4 case file
- Passphrase-gated console; open, rate-limited public intake (30/hour)
- Works with the server switched off — falls back to the last built artifacts

Add one honest note in small text: the commodity vertical runs on **real
Agmarknet data**; the egg and auto verticals use **real published reference rates**
with simulated observations, pending field collection.

## Slide 6 — Impact & Use Cases

**Who benefits**
- District supply officers and RTO enforcement desks — a ranked shortlist instead of an unreadable feed
- Consumers — a public reference for what a fair price actually is
- Honest traders — cleared by the same evidence that flags others

**Real-world applications:** essential-commodity price monitoring, autorickshaw
fare enforcement, festival and disaster-period profiteering checks, and
targeting of Uzhavar Sandhai inspections.

**Scaling:** the pipeline is district-agnostic. Adding a district is a data
question, not an engineering one — the same four detectors, the same contracts.
Reference rates already exist nationally through Agmarknet, NECC and state
gazette notifications.

**Sustainability:** the entire offline pipeline reproduces from committed source
data with no network access, and rebuilds are byte-identical — so any finding can
be re-derived and audited months later.

## Slide 7 — Challenges Faced

Present as problem → what we did. These are real engineering obstacles:

1. **The documented data source no longer existed.** Agmarknet has been rebuilt
   as a single-page app whose API sits behind a captcha. We did not attempt to
   bypass bot protection — we moved to the portal's official export and the
   data.gov.in API instead.
2. **The model learned to excuse manipulation.** With a market's own lagged price
   as a feature, the suspect market *never left the band* — the model simply
   predicted the collusive price. We removed own-price history entirely and
   refit in relative space.
3. **One bad market framed its honest neighbours.** Using a peer *mean*, the
   manipulated market raised the expected band for nearby honest markets and
   pushed them below it. Fixed with a leave-one-out median.
4. **The evidence floor was trivially beatable.** At ~50m grid resolution, one
   reporter walking 100m became a second "independent" witness. Locality
   generalisation closed it.
5. **One market appeared under 33 different names.** "Vellore" and "Vellore
   APMC"; "Katpadi (Uzhavar Sandhai )" three separate ways. Unresolved, a single
   market splits into several and appears in the queue repeatedly. A name
   normaliser reduced **33 raw names to 17 real markets**.
6. **A market that was not comparable.** One market sat ~50km away in a
   separately administered district and produced repeat flags across unrelated
   commodities — one market looking like four findings. Excluding it *improved*
   model coverage from 0.785 to 0.806.

## Slide 8 — Future Scope

- **Recover the supply signal.** The current export omits the arrivals column.
  With it, the cost-correlation measure works on commodities and the "was it a
  bad harvest?" defence becomes quantitative. It is the single highest-value
  addition.
- **Real observed prices for eggs and autos** — paired app-quote versus
  street-quote collection, where the gap between the two is itself the signal.
- **Time-of-day analysis for fares.** A genuine surge varies by hour; a fixed
  zone rate does not. The timestamps are already collected.
- **Multi-district and multi-state rollout**, with per-district peer groups so
  structurally different markets are compared fairly rather than excluded.
- **Officer feedback loop** — inspection outcomes fed back as labels, moving from
  unsupervised screening toward calibrated prioritisation.

## Slide 9 — Conclusion

A working, end-to-end system on real government data that turns 216,732 price
observations into a shortlist an officer can act on this week.

Reinforce the three things that make it defensible rather than merely clever:
- **Every flag is reconstructible by hand.** No black box, because an accusation
  must be explainable in a document.
- **The system refuses to act on thin evidence**, in code — one pattern is
  currently withheld for exactly that reason.
- **It flags for investigation. It never claims proof.** Sellers are identified
  only by pseudonymous location codes; no business name enters the pipeline.

Close on the thesis: *competitive prices track costs; collusive prices track each
other* — and the system measures precisely that difference.

## Slide 10 — Acknowledgements

- Team members and contributions: [FILL IN]
- Mentors: [FILL IN]
- **Data sources:** Agmarknet, Directorate of Marketing & Inspection, Government
  of India; National Egg Coordination Committee (NECC) — note that NECC suggested
  egg prices are *suggestive and not mandatory*; Tamil Nadu autorickshaw fare
  notification (Transport Department).
- **Open-source:** pandas, LightGBM, FastAPI, React, Recharts, Vite.
