# Backend World Wide Bistro

Proiectul are acum două variante de backend:

- **Local:** serverul Python și baza SQLite, potrivite pentru lucru pe calculator.
- **Netlify:** funcții serverless, bază Postgres persistentă și notificări SMTP. Fișierele funcțiilor rămân în afara folderului public `dist`.

## Publicare pe Netlify

1. Încarcă proiectul într-un repository Git și conectează-l la Netlify. Netlify folosește configurația din `netlify.toml`; comanda de build copiază în `dist` doar paginile, stilurile, scripturile și meniul PDF.
2. La prima publicare, Netlify detectează pachetul `@netlify/database` și migrarea `netlify/database/migrations/0001_create_requests.sql` și configurează baza de date pentru proiect. În interfața Netlify, verifică **Data & Storage → Database** și confirmă că baza este activă.
3. În **Project configuration → Environment variables**, adaugă:

   | Variabilă | Valoare |
   | --- | --- |
   | `ADMIN_USERNAME` | Un nume de utilizator ales de tine (poți folosi `admin`) |
   | `ADMIN_PASSWORD` | O parolă unică și lungă pentru panoul de administrare |
   | `SESSION_SECRET` | Un secret aleator de cel puțin 32 de caractere |
   | `SMTP_HOST` | De exemplu `smtp.gmail.com` |
   | `SMTP_PORT` | `587` pentru STARTTLS sau `465` pentru TLS |
   | `SMTP_USER` | Contul de e-mail autorizat să trimită notificări |
   | `SMTP_PASSWORD` | Parola de aplicație SMTP, păstrată doar în Netlify |
   | `SMTP_FROM` | Adresa expeditorului autorizat, de obicei aceeași cu `SMTP_USER` |
   | `BUSINESS_EMAIL` | `fe.worldwidebistro.srl@gmail.com` |

   Nu adăuga variabilele secrete în cod sau în repository. Pentru ca formularul să salveze cereri, sunt necesare baza de date și secretele de administrare. SMTP este opțional: fără el, cererile rămân salvate și apar în panou, iar site-ul indică numărul de telefon pentru confirmare.
4. Publică din nou după configurarea variabilelor. Apoi, pagina publică va fi la domeniul Netlify, iar panoul la `/admin`.

Autentificarea folosește cookie HttpOnly semnat, iar cererile publice și încercările de autentificare au limită per adresă IP. Rezervările nu se confirmă automat; echipa trebuie să contacteze clientul și să schimbe starea cererii din panou.

## Costuri Netlify

Codul și pachetele folosite nu percep taxe. Planul Netlify Free costă 0 $, dar serviciile platformei folosesc cote și credite lunare. Baza de date și funcțiile serverless sunt măsurate; dacă limita planului gratuit este atinsă, serviciile pot fi oprite până la următoarea perioadă de facturare. Verifică pagina de utilizare a contului după publicare și nu activa un plan plătit dacă dorești să păstrezi costul la 0 $.

## Pornire locală cu Python

1. Copiază `.env.example` în `.env`.
2. Schimbă `ADMIN_PASSWORD` și `SESSION_SECRET`. Configurează SMTP doar dacă vrei e-mailuri de notificare.
3. Pornește serverul:

   ```sh
   python3 server.py
   ```

4. Deschide `http://127.0.0.1:8000`; panoul local este la `http://127.0.0.1:8000/admin`.

Varianta locală salvează cererile în `data/requests.sqlite3`. Varianta Netlify folosește separat Postgres; datele dintr-un mediu nu sunt sincronizate automat cu celălalt.
