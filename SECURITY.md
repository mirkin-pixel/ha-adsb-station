# Security

## Reporting a vulnerability

Please do not report a security problem in a public issue, where anyone can read it before it is fixed.

Report it privately instead: on the [Security tab](https://github.com/mirkin-pixel/ha-adsb-station/security) of this repository, choose **Report a vulnerability**. Only the maintainer sees the report. Say what is affected, how to reproduce it, and which version you run.

You get an answer within a week. Once a fix is out, the report is published with credit to you, unless you would rather stay unnamed.

## What is in scope

The integration and its dashboard cards, as released here. Two parts are worth a closer look, as they take in data from outside: the cards show text that comes from aircraft and from servers on the internet, and the integration reads what the decoder and the feeders on your network serve.

Problems in Home Assistant itself, in HACS or in a decoder or feeder belong with those projects.

## Supported versions

Fixes go into the latest release. There are no fixes for older versions: updating is the way to get one.
