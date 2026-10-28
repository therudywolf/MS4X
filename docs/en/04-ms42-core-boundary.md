# 04. A safe code layer for the MS42: the rule and the boundary

A guideline for whoever puts own code into the free area of the MS42 0110C6. It is not a recipe and it ships no code: it is the rule a layer has to meet to be safe for a car that is not yours, what has to stay out, and how to prove the rule. The author's own layer is built to this rule and is not part of this repository.

## The rule

A function belongs in a layer for other people's cars only if all three hold:

1. it works on any factory 0110C6 image, not on one particular calibration;
2. it does not weaken a factory protection (throttle monitoring, knock control, component and overheat protection, the diagnostics);
3. with its switch off it gives factory behaviour, byte for byte in what the car does.

Everything else is a tune for one car, and a tune does not travel.

## What has to stay out

- the show layer in every form: exhaust pops and bangs, a two-step, idle effects, anything that cuts the spark while the fuel keeps flowing — on a car with a catalyst this is a melted catalyst and a fire risk;
- rolling anti-lag and anything built on the community launch-control hook;
- the calibration: knock, ignition timing, VANOS, the air-mass meter, the coolant maps;
- the EGAS diagnostic stretches;
- switching off the catalyst or the oxygen sensors;
- turning the knock sensors off;
- anything about the immobilizer (EWS).

## How to prove the rule

- Build the image with every switch off and run the factory functions the hooks sit in on the emulator (document 02), with the same inputs, against the stock image: the registers and the RAM the factory code writes have to match, instruction by instruction.
- Run `ms4x_core.py info` with the community patchlist on the result: the free area must show only your own ranges, and every community patch must read as applied or not applied, never changed otherwise.
- Keep the self-check: a layer that does not match its own reference must not run at all.
