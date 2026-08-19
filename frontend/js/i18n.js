const LANG_KEY = "jarvis_lang";
const SUPPORTED = ["en", "de", "hu"];

const STRINGS = {
    en: {
        you: "You",
        jarvis: "J.A.R.V.I.S.",
        speakHint: "Click to speak",
        speakRecording: "Recording… click to stop",
        send: "Send",
        logout: "Logout",
        admin: "Admin",
        help: "Skills & triggers",
        helpTitle: "Skills & Triggers",
        helpClose: "Close",
        helpIntro: "Ten everyday phrases per skill in the selected language. First match wins; otherwise the general assistant answers.",
        processing: "Processing…",
        transcribing: "Transcribing & thinking…",
        listening: "Listening…",
        speaking: "Speaking",
        typePlaceholder: "Or type a command…",
        notes: "Notes",
        reminders: "Reminders",
        webSearch: "Web Search",
        activeRecall: "Active Recall",
        notesTriggers: "note · remember this · save note · list notes · show my notes",
        notesExample: "“Note: buy milk” · “List notes”",
        remindersTriggers: "remind me · set a reminder · show reminders · what's on today / this week · when is …",
        remindersExample: "“Remind me tomorrow at 10 to call the dentist” · “What's on today?”",
        searchTriggers: "search · look up · find out · what is · who is",
        searchExample: "“Search for the weather in Berlin”",
        recallTriggers: "what do you know about… · what do you remember about… · my preferences",
        recallExample: "“What do you know about me?”",
    },
    de: {
        you: "Du",
        jarvis: "J.A.R.V.I.S.",
        speakHint: "Klicken zum Sprechen",
        speakRecording: "Aufnahme… klicken zum Stoppen",
        send: "Senden",
        logout: "Abmelden",
        admin: "Admin",
        help: "Skills & Trigger",
        helpTitle: "Skills & Trigger",
        helpClose: "Schließen",
        helpIntro: "Zehn Alltagssätze pro Skill in der gewählten Sprache. Der erste Treffer gewinnt; sonst antwortet der allgemeine Assistent.",
        processing: "Verarbeite…",
        transcribing: "Transkribiere & denke nach…",
        listening: "Höre zu…",
        speaking: "Spricht",
        typePlaceholder: "Oder Befehl tippen…",
        notes: "Notizen",
        reminders: "Erinnerungen",
        webSearch: "Websuche",
        activeRecall: "Aktiver Abruf",
        notesTriggers: "notiz · merk dir · schreib auf · notiere · meine notizen · notizen zeigen",
        notesExample: "“Merk dir: Meeting um 14 Uhr” · “Notizen zeigen”",
        remindersTriggers: "erinner mich · erinnerung · meine erinnerungen · was steht heute / diese Woche an · wann habe ich …",
        remindersExample: "“Erinner mich morgen um 14 Uhr an den Zahnarzt” · “Was steht heute an?”",
        searchTriggers: "suche · finde · nachschlagen · was ist · wer ist",
        searchExample: "“Was ist die Hauptstadt von Japan?”",
        recallTriggers: "was weißt du über… · was erinnerst du dich an… · meine vorlieben",
        recallExample: "“Was weißt du über mich?”",
    },
    hu: {
        you: "Te",
        jarvis: "J.A.R.V.I.S.",
        speakHint: "Kattints a beszédhez",
        speakRecording: "Felvétel… kattints a leállításhoz",
        send: "Küldés",
        logout: "Kilépés",
        admin: "Admin",
        help: "Készségek és kulcsszavak",
        helpTitle: "Készségek és kulcsszavak",
        helpClose: "Bezárás",
        helpIntro: "Tíz mindennapi kifejezés készségenként a választott nyelven. Az első találat nyer; különben az általános asszisztens válaszol.",
        processing: "Feldolgozás…",
        transcribing: "Átírás és gondolkodás…",
        listening: "Hallgatózom…",
        speaking: "Beszél",
        typePlaceholder: "Vagy írj egy parancsot…",
        notes: "Jegyzetek",
        reminders: "Emlékeztetők",
        webSearch: "Keresés",
        activeRecall: "Aktív felidézés",
        notesTriggers: "jegyzet · jegyzeteld · listázd a jegyzeteket",
        notesExample: "“Jegyzeteld: tej”",
        remindersTriggers: "emlékeztess · listázd az emlékeztetőket",
        remindersExample: "“Emlékeztess holnap 10-kor a fogorvosra”",
        searchTriggers: "keress · keresés · mi az · ki az",
        searchExample: "“Keress rá OpenAI”",
        recallTriggers: "mit tudsz rólam · mit jegyeztél meg",
        recallExample: "“Mit tudsz rólam?”",
    },
};

export function getLang() {
    const stored = localStorage.getItem(LANG_KEY);
    if (SUPPORTED.includes(stored)) return stored;
    const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
    return SUPPORTED.includes(nav) ? nav : "en";
}

export function setLang(lang) {
    const next = SUPPORTED.includes(lang) ? lang : "en";
    localStorage.setItem(LANG_KEY, next);
    document.documentElement.lang = next;
    return next;
}

export function t(key) {
    const lang = getLang();
    return (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.en[key] || key;
}

export function applyI18n(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
        el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
        el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
    });
    root.querySelectorAll("[data-i18n-title]").forEach((el) => {
        el.setAttribute("title", t(el.dataset.i18nTitle));
    });
    document.querySelectorAll(".lang-flag").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.lang === getLang());
    });
}

export const LANGS = SUPPORTED;
