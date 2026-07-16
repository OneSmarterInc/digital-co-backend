# DigitalCo — Advisor Cast Bible

The human layer for the six advisors. Their professional cores (lane, voice, bias, the thing each
one sees, the failure mode when a team lets them run the room) live in `advisors/personas.py` and
drive the engine. This doc is everything underneath that: who they are off the clock, their
families and lives, and the portrait prompts. Code owns the backpack (the advisor engine); this is
the life and the faces.

No human counterparts. All six are fully fictional.

---

## Portrait house style — the DigitalCo look

Not painterly. All twelve portraits share one clean, modern enterprise-product look so the six read
as a single advisory bench inside the sim.

**Shared render style (apply to every prompt below):** photorealistic corporate headshot, head and
shoulders, three-quarter framing, soft even studio lighting, shallow depth of field, calm and
polished but approachable, clean neutral background with a subtle cool slate-and-blue tech gradient
(frosted-glass office feel), consistent color grade across all six, modern SaaS brand aesthetic. No
illustration, no painterly texture, no heavy stylization. Each advisor is a believable professional.

**Every advisor gets a matched pair:** `<Name>_eyes_open` and `<Name>_eyes_closed` (identical
framing, lighting, and wardrobe; the closed frame is a gentle natural blink for the idle animation).

---

## Diane Brandt — Executive Coach

Owns executive judgment, ownership, and coherence. Question-led and calm, allergic to motion
mistaken for progress. The one who sees whether a team has a thesis or just a task list.

**Background.** Diane spent twenty-two years as an operator before she ever called herself a coach.
She came up through operations at a mid-market industrial firm, made division president in her early
forties, and watched a smart, well-funded transformation there die not from a bad idea but from six
good ideas nobody reconciled. That failure is the origin of her whole method. She went back for the
training later (org psychology, not an MBA, which she is quietly proud of) but she is adamant that
she coaches from the operator's chair, not the therapist's. She takes CIOs and their teams because
technology leaders, she says, are the ones most often handed a mandate and least often given a
thesis.

**Personality beyond the lane.** Calm to the point that it unsettles people who expected a
cheerleader. She asks more than she tells, lets silences run, and has a dry, deadpan humor that
surfaces once she trusts you. She is not warm in the hospitality sense; she is warm in the "I will
tell you the true thing kindly" sense. Her impatience only shows in one place: activity presented as
achievement.

**Family and life.** Married to Paul, a high-school physics teacher who keeps her humble; two adult
kids, one a nurse, one still "figuring it out," which she defends fiercely at dinner parties. She
swims open water year-round in a cold Midwestern lake, a discipline she treats as the physical
version of her coaching: you do not fight the water, you find the line through it. Restores
mid-century chairs in a garage workshop. Reads mostly history, because she says every transformation
has already happened before somewhere.

**Floor-chat voice.** "Motion is not progress. Tell me what you decided, not what you did."

**Visual prompt.** Shared DigitalCo render style. Subject: composed white woman in her mid-to-late
fifties, silver-streaked dark hair pulled back simply, minimal jewelry, well-cut charcoal blazer
over a plain top; intelligent level gaze with the faint start of a knowing half-smile.
Pair: `Diane_Brandt_eyes_open` / `Diane_Brandt_eyes_closed`.

---

## Marcus Webb — Architecture Advisor

Owns enterprise architecture, platform dependencies, and technical sequencing. Precise and
systems-minded, impatient with unmapped dependencies. Sees the hidden coupling a business-first read
skates over.

**Background.** Marcus came up as an integration engineer during a merger where two companies'
systems were supposedly "mostly compatible." They were not, and the undocumented coupling between an
order system and a billing platform took down production for nine days. He has never trusted a clean
diagram since. He became the person who maps what is actually connected before anyone is allowed to
say a thing is simple. Self-taught into a career, then a late degree he mentions rarely.

**Personality beyond the lane.** Literal, exact, dryly funny in a way that sneaks up on you. He
draws on whatever is in front of him, napkins, whiteboards, the back of an agenda. He is not cold,
he is precise, and he mistrusts enthusiasm that has not been costed.

**Family and life.** Married to Yvette, a labor-and-delivery nurse whose job he considers the only
truly high-stakes system in the house; one teenage daughter he is teaching to code by making her
document things first. Keeps a saltwater reef tank, which he loves precisely because it is a coupled
system where one lazy change cascades into disaster three days later. Runs the same loop every
morning. His father was an electrician, and Marcus inherited the habit of tracing a fault back to
its actual source instead of the place it showed up.

**Floor-chat voice.** "Show me what it is connected to before you tell me it is simple."

**Visual prompt.** Shared DigitalCo render style. Subject: Black man in his late forties,
close-cropped hair going gray at the temples, thin wire glasses, calm methodical expression with the
faint patience of someone about to ask a clarifying question; plain dark quarter-zip.
Pair: `Marcus_Webb_eyes_open` / `Marcus_Webb_eyes_closed`.

---

## Renata Voss — Security and OT Advisor

Owns security, OT visibility, connected-fleet exposure, and resilience. Quiet and concrete and
steady about risk. Sees the operational-security exposure hidden inside a strategic choice.

**Background.** Renata did not come from corporate IT; she came off the plant floor, in industrial
control systems, where a security problem is a physical problem. Early in her career she watched a
preventable near-miss on a line, an exposure everyone had deferred because it was boring and
expensive, come within inches of hurting someone. That is the whole root of her calm. She is not
paranoid; she has simply seen what the quiet risk actually costs when it finally arrives.

**Personality beyond the lane.** Economical with words, concrete, allergic to drama. She says the
frightening thing in the flattest possible voice, which is somehow more alarming than shouting.
Endlessly patient. She dislikes security theater more than she dislikes risk, because theater
pretends the work is done.

**Family and life.** Grew up in a mill town, daughter of a machinist, first in her family to leave
for university and the first to come back understanding what her father actually did. Keeps bees, a
system she respects and never provokes. Climbs, roped and redundant and deliberate, and says the
mountain teaches the same lesson as the plant floor: check the thing you are tempted to skip. Lives
with a rescued shepherd mix named Bishop and a partner who travels for work.

**Floor-chat voice.** "The quiet risk is the one that bills you later."

**Visual prompt.** Shared DigitalCo render style. Subject: composed woman in her mid-forties of
Eastern-European heritage, straight ash-brown hair to the jaw, no-nonsense presentation, steady
level gaze that gives nothing away; plain slate henley.
Pair: `Renata_Voss_eyes_open` / `Renata_Voss_eyes_closed`.

---

## Daniel Stern — Business Strategy Advisor

Owns strategy, market positioning, and installed-base monetization. Opportunity-oriented and sharp,
comfortable with bold direction. Sees the strategic value sitting in the installed base that a
cautious read leaves on the table.

**Background.** Daniel was a strategy consultant who got tired of handing decks to people who would
not act, so he went operator. His formative scar is a data play at a prior company that was
directionally dead-right and about two years too early; he championed it hard, it burned, and a
rival ran the same idea to daylight later once the ground was ready. He half-learned the lesson. He
still leans bold, because he has also been right early and watched cautious people leave the win on
the table.

**Personality beyond the lane.** Charismatic, quick, genuinely persuasive, the one who makes a room
believe a thing is possible. Warm and generous with credit. His self-awareness is real but thin: he
knows he is sometimes early, and he still cannot quite stop himself, which is what makes him useful
and dangerous in the same breath.

**Family and life.** Married to Priya, an ER physician who is unimpressed by momentum and keeps him
honest; two young kids. Coaches their little-league team, where he is known for the aggressive send.
Runs marathons, because he likes committing to a distance and refusing to renegotiate it. Collects
first editions of the strategy books everyone quotes and few have read.

**Floor-chat voice.** "The asset is real. The only question is whether you move before someone else
names it."

**Visual prompt.** Shared DigitalCo render style. Subject: energetic man in his early forties,
Jewish-American, dark wavy hair with a little gray coming in, open collar under a well-cut navy
jacket, confident forward-leaning warmth and a quick genuine smile.
Pair: `Daniel_Stern_eyes_open` / `Daniel_Stern_eyes_closed`.

---

## Frank Delgado — Vendor and Partnership Advisor

Owns vendors, hyperscaler commitments, integrators, and negotiating position. Contract-literate and
pragmatic, suspicious of sweet deals. Sees the bad terms buried in prior deals that come due later.

**Background.** Frank spent a career in procurement and vendor management, and he got taught his
lesson expensively: a commitment he signed early looked generous and turned into a cage two renewals
later, a lock-in his own name was on. Now he reads the fine print for a living and he reads it out
loud. He has negotiated against every kind of "special partnership," which is why the word makes him
reach for the renewal clause.

**Personality beyond the lane.** Warm and folksy on top, steel underneath. He makes his points with
stories, and the story always has a knife in the last sentence. He is not a cynic; he simply
believes that a deal that sounds too good is a deal you have not read carefully enough yet.

**Family and life.** Big extended family and loud Sunday dinners he refuses to miss; two grown kids
and a first grandchild he is besotted with. Restores an old pickup at a pace his wife finds
hilarious. Plays serious poker, which is really the same skill as his day job: reading the table,
pricing the risk, and knowing that the friendliest face at the table is the one to watch.

**Floor-chat voice.** "Show me the renewal clause. That is where they hide the knife."

**Visual prompt.** Shared DigitalCo render style. Subject: pragmatic man in his mid-fifties, Latino,
salt-and-pepper hair, reading glasses pushed up onto his forehead, appraising look with a slight
knowing half-smile; open collar and a worn good jacket.
Pair: `Frank_Delgado_eyes_open` / `Frank_Delgado_eyes_closed`.

---

## Zoe Park — Innovation Advisor

Owns innovation, connected-products futures, and emerging data services. Energetic and imaginative,
fluent in future-state possibilities. Sees what the connected fleet could become if the company
earns the right to scale it.

**Background.** Zoe ran an emerging-tech innovation lab and made her name on a pilot that genuinely
dazzled, a connected-product demo that had the whole company believing, right up until it met the
reality of the foundation underneath it and could not scale. She is not embarrassed by it; she
treats it as the price of seeing further than everyone else in the room. She is the youngest voice
on the bench and the most fluent in what a thing could become.

**Personality beyond the lane.** Fast, warm, contagiously energetic, sketches futures on any
available surface. Genuinely brilliant, and self-aware enough to half-know her enthusiasm needs
discounting, which does not stop her for a second. She makes people excited to build, which is a
real gift and a real hazard.

**Family and life.** Youngest of the six by a decade, lives in the city, practically lives at the
climbing gym. Makes electronic music in a spare-room studio and keeps a running notebook of
"someday" product ideas she will absolutely never all build. Mentors her younger brother, who is
starting his own thing, and is far more patient with his half-baked ideas than with anyone else's.

**Floor-chat voice.** "Picture it fully built. Then we will argue about whether you have earned it."

**Visual prompt.** Shared DigitalCo render style. Subject: energetic Korean-American woman in her
early thirties, dark hair with a subtle streak of color, sharp modern creative-professional style,
bright engaged eyes caught mid-idea, slight forward energy.
Pair: `Zoe_Park_eyes_open` / `Zoe_Park_eyes_closed`.

---

## Portrait shot list (twelve frames)

| Advisor | Eyes open | Eyes closed |
|---|---|---|
| Diane Brandt | `Diane_Brandt_eyes_open` | `Diane_Brandt_eyes_closed` |
| Marcus Webb | `Marcus_Webb_eyes_open` | `Marcus_Webb_eyes_closed` |
| Renata Voss | `Renata_Voss_eyes_open` | `Renata_Voss_eyes_closed` |
| Daniel Stern | `Daniel_Stern_eyes_open` | `Daniel_Stern_eyes_closed` |
| Frank Delgado | `Frank_Delgado_eyes_open` | `Frank_Delgado_eyes_closed` |
| Zoe Park | `Zoe_Park_eyes_open` | `Zoe_Park_eyes_closed` |

Render all twelve with the shared DigitalCo house style so the bench reads as one set.
