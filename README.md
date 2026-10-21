# Telegram Sender Bot

Bot do automatycznej wysyłki wiadomości na czaty Telegram według harmonogramu.

## Spis treści

- [Funkcje](#funkcje)
- [Struktura projektu](#struktura-projektu)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
- [Konfiguracja](#konfiguracja)
- [Uruchomienie](#uruchomienie)
- [Użytkowanie](#użytkowanie)
- [Bezpieczeństwo](#bezpieczeństwo)
- [Rozwiązywanie problemów](#rozwiązywanie-problemów)
- [Autorzy](#autorzy)

## Funkcje

- 🔐 Autoryzacja na koncie Telegram
- 📝 Tworzenie rozsyłek z tekstem, zdjęciem lub wideo
- 🎯 Wybór wielu czatów docelowych
- 🔍 Wyszukiwanie czatów po nazwie
- ⏰ Konfiguracja interwałów: raz na godzinę, raz dziennie lub własny interwał
- 📋 Podgląd aktywnych rozsyłek

## Struktura projektu

```
TgSender/
├── main.py            # punkt wejścia, logika bota
├── config.py          # wczytywanie konfiguracji ze zmiennych środowiskowych
├── database.py        # obsługa bazy danych (rozsyłki, sesje)
├── requirements.txt   # zależności projektu
├── .env.example       # wzór pliku konfiguracyjnego
├── .gitignore
└── README.md
```

## Wymagania

- Python 3.10 lub nowszy
- Menedżer pakietów `pip`
- Token bota od [@BotFather](https://t.me/BotFather)
- Dane `API_ID` i `API_HASH` z [my.telegram.org](https://my.telegram.org)
- Konto Telegram, z którego będą wysyłane wiadomości

## Instalacja

1. Sklonuj repozytorium:

   ```bash
   git clone https://github.com/dabwsnow/TgSender.git
   cd TgSender
   ```

2. (Zalecane) Utwórz i aktywuj środowisko wirtualne:

   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux / macOS
   venv\Scripts\activate         # Windows
   ```

3. Zainstaluj zależności:

   ```bash
   pip install -r requirements.txt
   ```

## Konfiguracja

1. Utwórz plik `.env` na podstawie `.env.example`:

   ```bash
   cp .env.example .env         # Linux / macOS
   copy .env.example .env       # Windows
   ```

2. Uzupełnij plik `.env`:

   | Zmienna     | Opis                                                         |
   |-------------|--------------------------------------------------------------|
   | `BOT_TOKEN` | Token Twojego bota otrzymany od [@BotFather](https://t.me/BotFather) |
   | `ADMIN_ID`  | Twój identyfikator Telegram (ID użytkownika)                 |
   | `API_ID`    | Identyfikator aplikacji z [my.telegram.org](https://my.telegram.org) |
   | `API_HASH`  | Hash aplikacji z [my.telegram.org](https://my.telegram.org)  |

### Jak zdobyć dane?

- **BOT_TOKEN** – napisz do [@BotFather](https://t.me/BotFather), użyj komendy `/newbot` i postępuj zgodnie z instrukcjami.
- **ADMIN_ID** – swoje ID możesz sprawdzić np. za pomocą bota [@userinfobot](https://t.me/userinfobot).
- **API_ID i API_HASH** – zaloguj się na [my.telegram.org](https://my.telegram.org), wybierz *API development tools* i utwórz aplikację.

## Uruchomienie

```bash
python main.py
```

## Użytkowanie

1. Uruchom bota komendą `/start`.
2. Zaloguj się na swoje konto Telegram.
3. Utwórz rozsyłkę: wybierz czaty (możesz skorzystać z wyszukiwarki) i ustaw interwał wysyłki.
4. Bot będzie automatycznie wysyłał wiadomości zgodnie z harmonogramem.
5. Aktywne rozsyłki możesz w każdej chwili przejrzeć w odpowiedniej sekcji bota.

## Bezpieczeństwo

- **Nigdy nie publikuj** pliku `.env` ani plików sesji Telegram – zawierają dane dostępowe do Twojego konta i bota. Plik `.env` jest wykluczony w `.gitignore`.
- Bot reaguje wyłącznie na użytkownika o identyfikatorze podanym w `ADMIN_ID`.
- Korzystaj z narzędzia zgodnie z [Regulaminem Telegrama](https://telegram.org/tos). Masowa wysyłka niechcianych wiadomości (spam) może skutkować ograniczeniem lub zablokowaniem konta.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Bot nie startuje | Sprawdź, czy plik `.env` istnieje i wszystkie zmienne są uzupełnione. |
| Błąd autoryzacji | Zweryfikuj `API_ID` i `API_HASH` oraz poprawność podanego numeru telefonu i kodu. |
| Bot nie odpowiada na `/start` | Upewnij się, że `ADMIN_ID` jest zgodny z Twoim ID i że token bota jest poprawny. |
| Błąd instalacji zależności | Sprawdź wersję Pythona (`python --version`) i zaktualizuj `pip`. |
| Wiadomości nie są wysyłane | Sprawdź, czy konto ma prawo pisać na wybranym czacie oraz czy rozsyłka jest aktywna. |

## Autorzy

Projekt powstał w dwuosobowym zespole:

| Osoba | Rola |
|-------|------|
| [dabwsnow](https://github.com/dabwsnow) | Programista – napisał kod bota (logika, baza danych, integracja z Telegramem) |
| Danylo | Tester i projektant – opracował koncepcję i wygląd bota (UX/design), przeprowadzał testy oraz zajmował się wszystkimi elementami projektu poza samym kodem |
