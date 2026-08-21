# User Guide – Skill Vocabulary (MVP)

On an empty database the first screen is **Create SuperUser**. After sign-in, Jarvis asks how you want to be addressed (after a forced password change, if any). That name is used in conversation.

Jarvis reacts to natural language. The phrases below are the **trigger patterns** that currently route a request to a dedicated skill instead of the general LLM path.

You can speak or type them. Matching is case-insensitive and works in English, German and Hungarian.

The Help panel (`?`) lists **ten everyday phrases per skill** for the language you pick with the flag (🇬🇧 / 🇩🇪 / 🇭🇺). The same catalog is at `GET /api/v1/skills/phrases?lang=en|de|hu`.

## Notes

| Intent | English | German | Hungarian |
|--------|---------|--------|-----------|
| Create | remember this, save a note, make a note, take a note, jot this down, write this down, add a note | merk dir, schreib auf, notiere das, speichere eine notiz, halte fest, neue notiz | jegyzeteld, jegyezd meg, írd fel, mentsd el, új jegyzet |
| List   | list my notes, show my notes, what notes do I have | meine notizen, notizen zeigen, welche notizen habe ich | listázd a jegyzeteket, mutasd a jegyzeteimet, milyen jegyzeteim vannak |

**Example**  
- “Note: buy milk tomorrow”  
- “Merk dir: Meeting um 14 Uhr”  
- “List notes”

## Reminders

| Intent | English | German | Hungarian |
|--------|---------|--------|-----------|
| Create | remind me, set a reminder, add a reminder, don't let me forget | erinner mich, erinnere mich, stell eine erinnerung, vergiss nicht | emlékeztess, állíts be emlékeztetőt, ne felejtsem el |
| List   | show my reminders, list reminders, do I have a reminder? | meine erinnerungen, habe ich eine Erinnerung? | listázd az emlékeztetőket, van emlékeztetőm? |
| Agenda | what's on today, is there anything for me today, what do I have today | was steht heute an, was habe ich heute | mi van ma a naptáramban, van ma valami |
| Lookup | when is …, when do I …, do I have a reminder for … | wann habe ich …, wann muss ich … | mikor van a … |
| Delete | delete the reminder …, cancel the reminder … | lösche die Erinnerung … | töröld az emlékeztetőt … |

Create needs a **verb** (`remind me`, `set`, `stell`, `emlékeztess`, …). A question that only contains the noun (`reminder` / `Erinnerung`) lists or looks up; it does not create. Delete cancels the pending reminder and forgets its short memory summary. A dropped letter in *delete* or the title (STT) still matches if one reminder is clearly the target.

**Date tokens on create** (optional): today/heute/ma, tomorrow/morgen/holnap, weekdays, numeric dates (`18.8.` / `18.8.2026`), “um 14 Uhr” / “at 14:00”, relative wait (`in 2 minutes` / `in 5 Minuten` / `2 perc múlva`). Clock times are **your local wall clock** (browser timezone). Jarvis stores UTC and speaks the local `HH:MM` back.

Skill replies (Reminders, Notes, Active Recall, Web Search) match the user's language (EN / DE / HU) so TTS is not English-on-German. The Help-panel flag is sent with voice and text turns as the STT/TTS hint.

When a reminder's time is reached **and the chat tab is open**, Jarvis shows a bubble and speaks it (poll about every 15s, and again when a turn finishes; no push, no WebSocket). A closed tab is silent — that is expected. Relative waits (`in 2 minutes`) and local clock times (`at 13:30`) both fire this way. A clock time already past locally is stored for **tomorrow**. A reminder with no time never fires.

**Example**  
- “Remind me tomorrow at 10 to call the dentist”  
- “Erinner mich morgen um 14 Uhr an den Zahnarzt”  
- “Is there anything for me today?”  
- “Do I have a reminder?”  
- “Was steht heute an?”  
- “Was steht nächste Woche an?”  
- “Wann habe ich meinen Termin bei der Arbeitsagentur?”  
- “Show reminders”  
- “Delete the reminder do I have a”

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

## Personal memory (Conversation → Semantic Memory)

These are **not** a routed skill. Say them in a normal sentence; Jarvis extracts a durable fact (original language, no translation). Then Active Recall can find it.

| English | German | Hungarian |
|---------|--------|-----------|
| my name is | ich heiße | a nevem |
| I live in | ich wohne in | lakom |
| I work as | ich arbeite als | dolgozom |
| I like | ich mag | szeretek |
| I prefer | ich bevorzuge | a kedvencem |
| I'm allergic to | ich bin allergisch | allergiás vagyok |
| my favourite | mein lieblings | származom |
| remember that I | ich komme aus | hívj |
| I am from | nenn mich | a születésnapom |
| my birthday is | mein geburtstag ist | imádom |

**Example:** “My name is Tony and I like espresso.” → later “What do you know about me?”

## Active Recall (personal knowledge)

| Intent | English | German | Hungarian |
|--------|---------|--------|-----------|
| Recall | what do you know about…, what is my name, what do you remember about…, my preferences | was weißt du über…, wie heiße ich, wie ist mein Name, meine vorlieben | mit tudsz rólam, mi a nevem, hogy hívnak, mire emlékszel |

**Example**  
- “What do you know about me?”  
- “What is my name?”  
- “Wie heiße ich?”  
- “Was weißt du über meine Vorlieben?”  
- “Recall what I told you about allergies”

## Notes on matching

- First matching skill wins (Active Recall is checked before Notes / Reminders / Web Search).
- If no skill matches, the request goes to the general LLM + memory path.
- Triggers are keyword / phrase patterns for the MVP. Reminder *create* may also ask the configured LLM to extract content and due date; regex remains the fallback if that call fails.
