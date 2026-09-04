const LANG_KEY = "jarvis_lang";
const CHAT_LANG_KEY = "jarvis_chat_lang";
const SUPPORTED = ["en", "de", "hu"];
const CHAT_LANGS = ["auto", "en", "de", "hu"];

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
        helpIntro: "Ten everyday phrases per skill in the GUI language. First match wins; otherwise the general assistant answers.",
        helpGuiLang: "These flags change user interface language only. Chat language is set in the chat window (Autodetect or a forced language).",
        chatLang: "Chat language:",
        chatLangAuto: "Autodetect",
        chatLangEn: "English",
        chatLangDe: "Deutsch",
        chatLangHu: "Magyar",
        processing: "Processing…",
        transcribing: "Transcribing & thinking…",
        listening: "Listening…",
        speaking: "Speaking",
        typePlaceholder: "How can I help you today?",
        notes: "Notes",
        reminders: "Reminders",
        webSearch: "Web Search",
        activeRecall: "Active Recall",
        personalFacts: "Personal memory",
        personalFactsIntro: "Say these in a normal sentence and Jarvis stores the fact (not a note or reminder).",
        notesTriggers: "note · remember this · save note · list notes · show my notes",
        notesExample: "“Note: buy milk” · “List notes”",
        remindersTriggers: "remind me · set a reminder · show reminders · what's on today / this week · when is …",
        remindersExample: "“Remind me tomorrow at 10 to call the dentist” · “What's on today?”",
        searchTriggers: "search · look up · find out · what is · who is",
        searchExample: "“Search for the weather in Berlin”",
        recallTriggers: "what do you know about… · what do you remember about… · my preferences",
        recallExample: "“What do you know about me?”",
        displayNameTitle: "How should Jarvis address you?",
        displayNameTagline: "Used in conversation. First name or nickname is enough.",
        displayNameLabel: "Preferred name",
        displayNamePlaceholder: "e.g. Tony",
        displayNameSubmit: "Continue",
        displayNameRequired: "Please enter a name.",
        displayNameFailed: "Could not save name",
        bootstrapStatusFailed: "Backend is not reachable. Start the API and reload this page.",
        allNotes: "All notes",
        allReminders: "All reminders",
        chatHistory: "Chats",
        newChat: "New chat",
        emptyNotes: "No notes yet.",
        emptyReminders: "No reminders yet.",
        emptyChats: "No chats yet.",
        openSidebar: "Menu",
        greetingHello: "Hello, {name}",
        addDocumentSoon: "Document upload later",
        deleteChat: "Delete chat",
        confirmDeleteChat: "Delete this chat? This cannot be undone.",
        editMessage: "Edit message",
        cancelEdit: "Cancel",
        saveEdit: "Save",
        editFailed: "Could not save the edit",
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
        helpIntro: "Zehn Alltagssätze pro Skill in der GUI-Sprache. Der erste Treffer gewinnt; sonst antwortet der allgemeine Assistent.",
        helpGuiLang: "Diese Flaggen ändern nicht die Chat-Sprache selbst, nur die Sprache der Benutzeroberfläche. Die Chatsprache stellst du im Chatfenster ein: Autodetect oder eine feste Sprache.",
        chatLang: "Chat-Sprache:",
        chatLangAuto: "Autodetect",
        chatLangEn: "English",
        chatLangDe: "Deutsch",
        chatLangHu: "Magyar",
        processing: "Verarbeite…",
        transcribing: "Transkribiere & denke nach…",
        listening: "Höre zu…",
        speaking: "Spricht",
        typePlaceholder: "Womit kann ich dir helfen?",
        notes: "Notizen",
        reminders: "Erinnerungen",
        webSearch: "Websuche",
        activeRecall: "Aktiver Abruf",
        personalFacts: "Persönliches Gedächtnis",
        personalFactsIntro: "Sag das in einem normalen Satz – Jarvis speichert den Fakt (keine Notiz, keine Erinnerung).",
        notesTriggers: "notiz · merk dir · schreib auf · notiere · meine notizen · notizen zeigen",
        notesExample: "“Merk dir: Meeting um 14 Uhr” · “Notizen zeigen”",
        remindersTriggers: "erinner mich · erinnerung · meine erinnerungen · was steht heute / diese Woche an · wann habe ich …",
        remindersExample: "“Erinner mich morgen um 14 Uhr an den Zahnarzt” · “Was steht heute an?”",
        searchTriggers: "suche · finde · nachschlagen · was ist · wer ist",
        searchExample: "“Was ist die Hauptstadt von Japan?”",
        recallTriggers: "was weißt du über… · was erinnerst du dich an… · meine vorlieben",
        recallExample: "“Was weißt du über mich?”",
        displayNameTitle: "Wie soll Jarvis dich ansprechen?",
        displayNameTagline: "Damit wirst du im Gespräch angesprochen. Vorname oder Spitzname reicht.",
        displayNameLabel: "Bevorzugter Name",
        displayNamePlaceholder: "z. B. Tony",
        displayNameSubmit: "Weiter",
        displayNameRequired: "Bitte einen Namen eingeben.",
        displayNameFailed: "Name konnte nicht gespeichert werden",
        bootstrapStatusFailed: "Backend nicht erreichbar. API starten und diese Seite neu laden.",
        allNotes: "Alle Notizen",
        allReminders: "Alle Erinnerungen",
        chatHistory: "Chats",
        newChat: "Neuer Chat",
        emptyNotes: "Noch keine Notizen.",
        emptyReminders: "Noch keine Erinnerungen.",
        emptyChats: "Noch keine Chats.",
        openSidebar: "Menü",
        greetingHello: "Hallo, {name}",
        addDocumentSoon: "Dokument-Upload später",
        deleteChat: "Chat löschen",
        confirmDeleteChat: "Diesen Chat löschen? Das lässt sich nicht rückgängig machen.",
        editMessage: "Nachricht bearbeiten",
        cancelEdit: "Abbrechen",
        saveEdit: "Speichern",
        editFailed: "Bearbeiten fehlgeschlagen",
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
        helpIntro: "Tíz mindennapi kifejezés készségenként a felület nyelvén. Az első találat nyer; különben az általános asszisztens válaszol.",
        helpGuiLang: "Ezek a zászlók csak a felhasználói felület nyelvét váltják. A csevegés nyelvét a chat ablakban állítod (autodetect vagy rögzített nyelv).",
        chatLang: "Csevegés nyelve:",
        chatLangAuto: "Autodetect",
        chatLangEn: "English",
        chatLangDe: "Deutsch",
        chatLangHu: "Magyar",
        processing: "Feldolgozás…",
        transcribing: "Átírás és gondolkodás…",
        listening: "Hallgatózom…",
        speaking: "Beszél",
        typePlaceholder: "Miben segíthetek?",
        notes: "Jegyzetek",
        reminders: "Emlékeztetők",
        webSearch: "Keresés",
        activeRecall: "Aktív felidézés",
        personalFacts: "Személyes memória",
        personalFactsIntro: "Mondd el egy mondatban – a Jarvis elmenti a tényt (nem jegyzet, nem emlékeztető).",
        notesTriggers: "jegyzet · jegyzeteld · listázd a jegyzeteket",
        notesExample: "“Jegyzeteld: tej”",
        remindersTriggers: "emlékeztess · listázd az emlékeztetőket",
        remindersExample: "“Emlékeztess holnap 10-kor a fogorvosra”",
        searchTriggers: "keress · keresés · mi az · ki az",
        searchExample: "“Keress rá OpenAI”",
        recallTriggers: "mit tudsz rólam · mit jegyeztél meg",
        recallExample: "“Mit tudsz rólam?”",
        displayNameTitle: "Hogyan szólítson a Jarvis?",
        displayNameTagline: "Ezt a nevet használja a beszélgetésben. Keresztnév vagy becenév elég.",
        displayNameLabel: "Megszólítás",
        displayNamePlaceholder: "pl. Tony",
        displayNameSubmit: "Tovább",
        displayNameRequired: "Adj meg egy nevet.",
        displayNameFailed: "A nevet nem sikerült menteni",
        bootstrapStatusFailed: "A backend nem elérhető. Indítsd el az API-t, majd töltsd újra ezt az oldalt.",
        allNotes: "Összes jegyzet",
        allReminders: "Összes emlékeztető",
        chatHistory: "Beszélgetések",
        newChat: "Új chat",
        emptyNotes: "Még nincs jegyzet.",
        emptyReminders: "Még nincs emlékeztető.",
        emptyChats: "Még nincs beszélgetés.",
        openSidebar: "Menü",
        greetingHello: "Szia, {name}",
        addDocumentSoon: "Dokumentumfeltöltés később",
        deleteChat: "Chat törlése",
        confirmDeleteChat: "Törlöd ezt a chatet? Ez nem vonható vissza.",
        editMessage: "Üzenet szerkesztése",
        cancelEdit: "Mégse",
        saveEdit: "Mentés",
        editFailed: "A szerkesztés nem sikerült",
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

export function getChatLang() {
    const stored = localStorage.getItem(CHAT_LANG_KEY);
    return CHAT_LANGS.includes(stored) ? stored : "auto";
}

export function setChatLang(lang) {
    const next = CHAT_LANGS.includes(lang) ? lang : "auto";
    localStorage.setItem(CHAT_LANG_KEY, next);
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
        const label = t(el.dataset.i18nTitle);
        el.setAttribute("title", label);
        el.setAttribute("aria-label", label);
    });
    document.querySelectorAll(".lang-flag").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.lang === getLang());
    });
}

export const LANGS = SUPPORTED;
export const CHAT_LANGUAGE_OPTIONS = CHAT_LANGS;
