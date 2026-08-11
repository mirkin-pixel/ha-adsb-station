# Asking out loud

"What is flying over?" is a better question to ask a room than to look up on a dashboard — you ask it while looking out of the window. Assist can answer five of them, from your own receiver, without a single request leaving your network.

| Ask | And it says |
|---|---|
| *What is flying over?* | Which aircraft is overhead, and how high |
| *How many aircraft can you hear?* | How many are nearby, and how many in all |
| *What is the nearest aircraft?* | How far away it is, and in which direction |
| *Are there any helicopters nearby?* | Military traffic, helicopters or drones in range |
| *Where is it going?* | Where the aircraft overhead came from and is heading |

Answers use the names from the [shipped tables](decoders.md#names-for-the-codes), so it says "KLM 123" and not "kilo lima mike one two three", and they follow the unit system of your Home Assistant rather than the language: metres and kilometres, or feet and miles.

English and Dutch are spoken; a question in any other language is answered in English.

There are two ways to wire this up, and they end at the same five answers.

## An automation, with no files at all

Home Assistant lets an automation own its sentences. Write them where you can see them, ask this integration for the answer, and say it back:

```yaml
automation:
  triggers:
    - trigger: conversation
      command:
        - "what is flying over"
        - "what is above me"
  actions:
    - action: adsb_station.speak
      data:
        question: overhead
      response_variable: spoken
    - set_conversation_response: "{{ spoken.speech }}"
```

Nothing is written to your configuration directory, nothing needs a restart, and you can edit the sentences in the interface. `question` is one of `overhead`, `count`, `closest`, `traffic` or `route`; the traffic one also takes `kind`, which is `military`, `helicopter` or `drone`.

The wording is still ours. `adsb_station.speak` hands back a finished sentence — the callsign spelled out or the airline named, the height rounded, the units and the decimal point right for the language — so the automation is three lines and not a template full of `round()`.

## The sentence files, so Assist knows the questions itself

The other way needs no automations: Assist recognises all five out of the box, in both languages, including phrasings you did not think to write down.

The catch is where those sentences have to live. Home Assistant reads them from your **configuration directory alone**, so an integration cannot bring its own; they ship inside it and have to be copied once.

```
custom_components/adsb_station/sentences/en/adsb_station.yaml  →  custom_sentences/en/adsb_station.yaml
custom_components/adsb_station/sentences/nl/adsb_station.yaml  →  custom_sentences/nl/adsb_station.yaml
```

Or let the integration copy them, if you would rather not go looking:

```yaml
- action: adsb_station.install_sentences
```

Be plain about what that does: **it writes two files into your configuration directory** and overwrites them if they are already there. It is the same copy you would make by hand, and nothing else is touched.

Either way Assist reads its sentences at startup, so run `conversation.reload` or restart afterwards. Then try it under **Settings → Voice assistants**, and ask it with an empty sky as well — that is the answer that comes up most often.

If two of your entries read an antenna, the first by name answers. Assist is for a quick question; the [services](services.md) are there when it has to be exact.
