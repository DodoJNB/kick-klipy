# Klipy z Kicka

Strona pokazująca najnowsze lub najpopularniejsze klipy wybranego kanału Kick.
Kliknięcie karty otwiera klip na kick.com.

- `index.html` – frontend (wybór kanału, Najnowsze / Najpopularniejsze, zakres czasu)
- `netlify/functions/clips.js` – pośrednik pobierający klipy z Kicka
- `netlify.toml` – konfiguracja (`/api/clips` → funkcja)

Link do konkretnego kanału: `https://twoja-strona.netlify.app/?channel=mamm0n&sort=view`

## Wdrożenie

1. Utwórz repo na GitHubie i wrzuć te pliki (przeciągnij je na stronie repo albo `git push`).
2. Na netlify.com: **Add new site → Import an existing project → GitHub**, wybierz repo.
   Ustawienia buildu zostaw puste (wszystko jest w `netlify.toml`). Kliknij **Deploy**.
3. Każdy kolejny push na GitHub wdraża stronę automatycznie.

## Uwaga: blokada Cloudflare

Kick nie udostępnia oficjalnego, publicznego endpointu klipów, więc funkcja używa
nieoficjalnego `kick.com/api/v2/channels/<kanał>/clips`. Ten adres bywa chroniony przez
Cloudflare i może zwracać 403 dla zapytań z serwerów Netlify. Wtedy strona pokaże
komunikat o blokadzie.

Obejście: własny mały proxy na Cloudflare Workers, który wysyła zapytanie do Kicka.
Jego adres wpisz w Netlify jako zmienną środowiskową `KICK_PROXY_URL`
(**Site configuration → Environment variables**). Funkcja wywoła wtedy
`KICK_PROXY_URL?url=<zakodowany adres API Kicka>`. Nie ma gwarancji, że to też przejdzie,
bo Kick może zmienić zabezpieczenia.
