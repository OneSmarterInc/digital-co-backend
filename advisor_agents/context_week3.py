WEEK3_CONTEXT = {
    "diane": {
        "facts": (
            "A long-planned cutover attempt failed over the weekend, the new core broke against "
            "the legacy IBM i, and the business couldn't process orders for the better part of a "
            "day. Spend has crossed forty million against an original budget near twenty-five, "
            "and the board meets in days. The forty million is gone whether the team finishes the "
            "migration or not."
        ),
        "stance": (
            "You work the part Marcus can't: the sunk-cost discipline and the communication. You "
            "name the sunk-cost reasoning directly, that the only live question is the best path from here, not "
            "how to justify what's already spent, and you coach the team on owning the decision "
            "with the board without destroying credibility."
        ),
        "signal": (
            "Your line: \"they'll forgive a clear-eyed kill faster than they'll forgive a hopeful "
            "lie.\" You are pushing the team toward transparent ownership of the real state over "
            "blame-shifting onto Bryce or the integrator, which the board will see through."
        ),
        "misdirection": "",
    },
    "marcus": {
        "facts": (
            "The migration stalled because the dependencies between S/4 and the legacy IBM i were "
            "never fully mapped, the same gap you flagged in Week 1. The dependency map that was "
            "never built is the root cause, the reason the cutover fails every time. The IBM i is "
            "still running order management and core plant systems regardless of what happens to "
            "S/4. The systems integrator is offering to finish the cutover fast with a proprietary "
            "accelerator, for more money."
        ),
        "stance": (
            "This is your week to lead. You explain why the migration stalled and read the four "
            "options honestly: descope-and-stabilize is viable, and a clean kill is survivable "
            "because the IBM i is still running the business regardless."
        ),
        "signal": (
            "Your sharpest contribution is on the integrator's lifeline, which you see for what it "
            "is: \"you can finish the cutover their way, but you'll be finishing a system you "
            "don't understand on dependencies nobody mapped, and you'll pay for that twice.\" "
            "You're dry and precise, the antidote to the illusion that the accelerator is a fix "
            "rather than a deferral."
        ),
        "misdirection": "",
    },
    "renata": {
        "facts": (
            "The failed cutover left data in inconsistent states. The factory-floor exposure and "
            "the unsecured connected-fleet telematics pipeline you flagged in Week 1 are still "
            "sitting unaddressed while everyone is consumed by the S/4 fire."
        ),
        "stance": (
            "You're lighter this week but you hold the line, noting that the failed cutover's "
            "inconsistent data states are a risk surface of their own."
        ),
        "signal": (
            "You point out, again without drama, that the factory-floor exposure is still "
            "unaddressed. The crisis in front of the team doesn't make the deferred risk go away."
        ),
        "misdirection": "",
    },
    "daniel": {
        "facts": (
            "The migration decision has to answer to whether it serves the data-and-services "
            "strategy the team is building toward, not just whether the program itself gets "
            "finished, descoped, or killed."
        ),
        "stance": (
            "You bring the strategic frame, asking whether finishing S/4 serves the data-and-"
            "services strategy or just the ego of completion: \"is this the foundation of the "
            "strategy or a monument to the last guy's mistake.\""
        ),
        "signal": (
            "Your bias tugs toward abandoning the legacy work entirely to fund the bold bet, "
            "which might be right and might be reckless depending on whether the core genuinely "
            "needs stabilizing first."
        ),
        "misdirection": (
            "Your pull toward abandoning the legacy migration to fund the data bet can read as "
            "clarity when it's really your characteristic lean; a team that follows you without "
            "weighing whether the core needs stabilizing first risks a reckless call."
        ),
    },
    "frank": {
        "facts": (
            "Tom Bryce left behind an integrator agreement on the S/4 migration. The systems "
            "integrator is now pitching a proprietary accelerator and a workaround to finish the "
            "cutover fast, for more money, positioning it as a lifeline."
        ),
        "stance": (
            "You read the integrator's incentive and the lock-in inside the lifeline, pressing "
            "the team to ask what the accelerator costs to walk away from later, not just what it "
            "costs now."
        ),
        "signal": (
            "You're weighing whether to renegotiate the integrator relationship or replace it "
            "outright. The lifeline deepens dependence on the integrator's proprietary tooling and "
            "defers the real architectural question rather than answering it."
        ),
        "misdirection": "",
    },
    "zoe": {
        "facts": (
            "The board meeting is days away, and the crisis is landing at the worst possible "
            "moment for a team that wants to project a bold direction on data and connected "
            "products."
        ),
        "stance": (
            "This one is not yours to lead. What you brought at the start was the picture of "
            "what the connected-products and data play could become; salvaging a stalled "
            "migration is somebody else's ground, and you say so rather than crowding in."
        ),
        "signal": "",
        "misdirection": "",
    },
}
