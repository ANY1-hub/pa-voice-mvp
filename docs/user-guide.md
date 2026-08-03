# User Guide – Skill Vocabulary (MVP)

Jarvis reacts to natural language. The phrases below are the **trigger patterns** that currently route a request to a dedicated skill instead of the general LLM path.

You can speak or type them. Matching is case-insensitive and works in English, German and Hungarian.

## Notes

| Intent | English | German | Hungarian |
|--------|---------|--------|-----------|
| Create | note, remember this, save note | notiz, merk dir, schreib auf, notiere | jegyzet, jegyzeteld |
| List   | list notes, show notes, show my notes, what notes | meine notizen, notizen zeigen | listázd a jegyzeteket |

**Example**  
- “Note: buy milk tomorrow”  
- “Merk dir: Meeting um 14 Uhr”  
- “List notes”

## Reminders

| Intent | English | German | Hungarian |
|--------|---------|--------|-----------|
| Create | remind me, reminder, set a reminder | erinner mich, erinnerung, stell eine erinnerung | emlékeztess |
| List   | list reminders, show reminders, what reminders | meine erinnerungen, erinnerungen zeigen, zeig mir die erinnerungen | listázd az emlékeztetőket |
| Agenda | what's on today, this week, next week, this month | was steht heute an, diese Woche, nächste Woche, diesen Monat | – |
| Lookup | when is …, when do I … | wann habe ich …, wann muss ich … | – |

**Date tokens on create** (optional): today/heute, tomorrow/morgen, weekdays, “um 14 Uhr” / “at 14:00”.

**Example**  
- “Remind me tomorrow at 10 to call the dentist”  
- “Erinner mich morgen um 14 Uhr an den Zahnarzt”  
- “Was steht heute an?”  
- “Was steht nächste Woche an?”  
- “Wann habe ich meinen Termin bei der Arbeitsagentur?”  
- “Show reminders”

## Web Search

| Intent | English | German | Hungarian |
|--------|---------|--------|-----------|
| Search | search, google, look up, find out, what is, who is | suche, finde, nachschlagen, was ist, wer ist | keress, keresés, mi az, ki az |

Longer prefixes that are stripped automatically:  
`search for`, `look up`, `find out`, `google for`, `suche nach`, `finde heraus`, `keress rá`.

**Example**  
- “Search for the weather in Berlin”  
- “Was ist die Hauptstadt von Japan?”  
- “Keress rá OpenAI”

## Active Recall (personal knowledge)

| Intent | English | German |
|--------|---------|--------|
| Recall | what do you know about…, what do you remember about…, recall what you know about…, my preferences | was weißt du über…, was erinnerst du dich an…, erinnere mich an…, meine vorlieben |

**Example**  
- “What do you know about me?”  
- “Was weißt du über meine Vorlieben?”  
- “Recall what I told you about allergies”

## Notes on matching

- First matching skill wins (Active Recall is checked before Notes / Reminders / Web Search).
- If no skill matches, the request goes to the general LLM + memory path.
- Triggers are deliberately simple keyword / phrase patterns for the MVP. More robust NLU can be added later.
