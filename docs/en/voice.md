# Asking out loud

"What is flying over?" is a better question to ask a room than to look up on a dashboard — you ask it while looking out of the window. Assist can answer ten of them, from your own receiver, without a single request leaving your network.

| Ask | And it says |
|---|---|
| *What is flying over?* | Which aircraft is overhead, and how high |
| *How many aircraft can you hear?* | How many are nearby, and how many in all |
| *What is the nearest aircraft?* | How far away it is, and in which direction |
| *Are there any helicopters nearby?* | Military traffic, helicopters or drones in range |
| *Where is it going?* | Where the aircraft overhead came from and is heading |
| *What just flew over?* | Which aircraft came over last, how long ago and how high |
| *What is the highest plane?* | Which aircraft flies highest, and where |
| *What is flying fastest?* | Which aircraft flies fastest, and how fast |
| *How far does the antenna reach?* | Which aircraft is furthest away: how far the station hears right now |
| *Is there an emergency up there?* | Whether any aircraft reports an emergency, and which |

Answers use the names from the [shipped tables](decoders.md#names-for-the-codes), so it says "KLM 123" and not "kilo lima mike one two three", and they follow the station's [units](configuration.md#units) rather than the language: metres and kilometres, feet and nautical miles, or feet and miles.

English and Dutch are spoken; a question in any other language is answered in English.

*What just flew over?* is for the aircraft you heard and only asked about once it had gone. It names the aircraft whose closest approach is the most recent one behind you, counted from that moment. One still on its way in has not come over yet, so for that one you hear what is overhead now. The station remembers an aircraft for ten minutes after it was last seen, and nothing over a restart, so after ten quiet minutes, or just after a restart, it says it has heard nothing come over.

There are two ways to wire this up, and they end at the same ten answers. An [AI assistant](#an-ai-assistant) gets them without either.

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

Nothing is written to your configuration directory, nothing needs a restart, and you can edit the sentences in the interface. `question` is one of `overhead`, `count`, `closest`, `traffic`, `route`, `last_passage`, `highest`, `fastest`, `furthest`, `emergency` or `aircraft`; the traffic one also takes `kind`, which is `military`, `helicopter` or `drone`.

`aircraft` is about one aircraft you name in the field of that name, by hex code, callsign or registration, such as the one a [watchlist](watchlist.md) event is about: *"KLM 123, a Boeing 737-800, is 22.3 kilometres to the north, 3,700 metres up and climbing."*, with where it is flying from and to when the route is known. It is an action only: Assist has no sentences for it, as a callsign is not something it hears reliably.

The wording is still ours. `adsb_station.speak` hands back a finished sentence — the callsign spelled out or the airline named, the height rounded, the units and the decimal point right for the language — so the automation is three lines and not a template full of `round()`.

## The sentence files, so Assist knows the questions itself

The other way needs no automations: Assist recognises all ten out of the box, in both languages, including phrasings you did not think to write down.

The catch is where those sentences have to live. Home Assistant reads them from your **configuration directory alone**, so an integration cannot bring its own; they ship inside it and have to be copied once.

```
custom_components/adsb_station/sentences/en/adsb_station.yaml  →  custom_sentences/en/adsb_station.yaml
custom_components/adsb_station/sentences/nl/adsb_station.yaml  →  custom_sentences/nl/adsb_station.yaml
```

Or let the integration copy them, if you would rather not go looking:

```yaml
- action: adsb_station.install_sentences
```

Be plain about what that does: **it writes two files into your configuration directory** and overwrites them if they are already there. It is the same copy you would make by hand, and nothing else is touched. Because it writes into your configuration, only an administrator can run it.

Either way Assist reads its sentences at startup, so run `conversation.reload` or restart afterwards. Then try it under **Settings → Voice assistants**, and ask it with an empty sky as well — that is the answer that comes up most often.

The copy does not follow the integration. When an update adds a question, copy the files again, or run `adsb_station.install_sentences` again, and reload; until then Assist knows only the questions of the version you copied.

If two of your entries read an antenna, the first by name answers. Assist is for a quick question; the [services](services.md) are there when it has to be exact. To ask a second station, give `adsb_station.speak` its `config_entry` in an automation with a sentence of your own, as [above](#an-automation-with-no-files-at-all).

## An AI assistant

A voice assistant that talks through an AI model, such as OpenAI, Google Gemini, Anthropic or Ollama, with **Assist** ticked in its settings, gets the ten questions as tools, plus one more: what one aircraft you name is, where it is and where it is going, by callsign, registration or hex code. So *"Where is KLM 123 now?"* works there, though Assist itself has no sentence for it. The model picks the question and says the answer in its own words; the numbers come from your receiver, and the tools only read.

This needs no sentence files. From Home Assistant 2026.10 the integration offers the tools itself; before that, Home Assistant handed them over on its own.
