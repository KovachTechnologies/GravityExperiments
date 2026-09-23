# Computational Theory of Gravity — laboratory notes

This repository holds the lab work used to test predictions of the **computational theory of gravity (CTG)**.

CTG treats gravity as an emergent, computational process rather than a primitive force: spacetime and attraction are what a discrete informational substrate does when it organizes matter. If that picture is right, gravity is not sealed off from the rest of physics. In particular, it should be possible — in principle — to couple to it through the electromagnetic configuration of ordinary materials, and to look for a small, local gravitational signature in a bench-top apparatus.

That is the claim this repo exists to confront. It is not a theory paper. It is the place where those predictions are turned into protocols, raw traces, analysis code, and dated write-ups.

## What is in scope

Each campaign asks a narrow question of the form: *if this configuration of fields and matter is doing what CTG says it is doing, what should a sensor see?*

Two families of measurement are the current workhorses. Neither is exclusive; both will be reused or replaced as later campaigns need.

- **Scalar / force channel.** A calibrated weight or similar scalar sensor logged against a clock, with the high-voltage supply on the sample either off (control) or on.
- **Optical / geometric channel.** A probe beam that interacts with the sample and lands on a screen or detector. Spot position, shape, and halo are reduced frame by frame.

Supporting pieces — TCP ingest from the measuring device, plot scripts, trackers — live next to the data they serve. They are tools, not results.

## How the repo is organized

Experiments are added **by date**. A given day gets its own note, data, and figures. This file does not recap those campaigns and will not be updated with their numbers.

When a new series is taken, add a new dated note. Do not fold it into this intro, but add a README.md explaining the experiment, and insure that the results are analyzed and discussed, perhaps in an `EXPERIMENTS.md` or `RESULTS.md` file

## How to read a campaign note

A useful note answers four things and stops:

1. **Prediction.** What CTG (or the working hypothesis derived from it) said should happen when the supply came on.
2. **Protocol.** What was actually done — windows, polarity, rest between takes, whether the switch time is in the file.
3. **Controls.** Supply-off takes, sham switches, and anything else that can produce the same trace without a field.
4. **Result.** What repeated across takes, what did not, and what the channel can and cannot claim at its present sensitivity.

A single interesting trace is not a detection. A null that does not beat the control floor is not a refutation of CTG as a whole; it is a bound on *that* geometry and *that* protocol.

## Working rules

- Log the protocol into the data (start, voltage on/off, polarity, gap since the last take). Inferring the switch from the trace is how campaigns get misread.
- Prefer a fixed window and enough rest between takes that leftover from the previous run is not the story.
- Judge time series before histograms. A narrow peak can sit at zero or far from it; only the clock tells you which.
- Keep analysis code next to the campaign it belongs to. Regenerating a figure should be one command from the dated note.

## Status

This is an active lab notebook, not an archive. Campaigns will accumulate by date. The intro stays here so the root of the repo still says *why* the work is being done after those dates pile up.
