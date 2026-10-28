# Verifica eseguita il 12 ottobre 2026

## Aggiornamento 13 ottobre 2026

- Corretto errore HTTP 401 causato dall’invio di un token TMDb come chiave v3: riconoscimento automatico e header Bearer.
- Ricerca reale serie TV con credenziale già configurata: 12 risultati e locandina scaricata.
- 13 test superati, inclusi entrambi i metodi di autenticazione, selezione risultati nella GUI e default 16 frammenti.
- Nuova build in `dist-aggiornata`, senza arrestare o sovrascrivere l’eseguibile della sessione aperta.

- Ambiente virtuale Python 3.12.6 e PySide6 6.8.3; dipendenze installate e versioni registrate. `pip check` riuscito.
- Test su nomi riservati, Unicode, collisioni, metadati, DRM, playlist, URL e parsing progresso.
- Test di errore URL non supportato, comando di analisi senza download e chiave TMDb mancante.
- Test reale della GUI PySide6 con video sintetico di due secondi, generato da FFmpeg e servito da un server HTTP locale: analisi yt-dlp, verifica strumenti, inserimento in coda e download MP4 completati.
- Screenshot `Verifica-interfaccia.png` esaminato: campi, coda, stato e pulsanti visibili.
- Nove test automatici superati. Build Windows PyInstaller in `dist/MovieDownloader`; EXE avviato, finestra Movie Downloader presente e processo responsivo. Verifica strumenti riuscita anche nell’EXE. PySide6 6.8.3 è fissato per evitare l’errore DLL osservato nella build con 6.12.0.

Ricerca reale TMDb e download da servizi esterni non verificati: mancano la chiave API e un URL autorizzato fornito dall’utente. Pausa/ripresa disponibile come arresto e riavvio con parziali; la compatibilità dipende dalla sorgente. Nessuna garanzia di supporto di ogni sito da parte della copia yt-dlp 2025.09.26.


## Redesign 28 ottobre 2026

- Tema scuro fumé con superfici semitrasparenti interne, bordi sottili, icone vettoriali e accenti azzurri. Comandi finestra nativi di Windows.
- Ricerca e metadati a sinistra, opzioni download a destra; disposizione verticale su finestre più strette. Locandine con altezza protetta e scorrimento orizzontale.
- Riepilogo del titolo selezionato, contatore della coda, interruttore sottotitoli, selettori rapidi italiano/inglese e opzioni avanzate richiudibili. Restano disponibili lingue personalizzate e frammenti.
- Localizzazioni inglese/italiano; preferenze, cartelle e coda esistenti mantenute.
- 19 test automatici superati. Layout verificato a 1440×900, 1060×740 e 860×600 senza scorrimento orizzontale della pagina.
- Ricerca TMDb reale verificata: 12 risultati con locandine. Analisi, coda e download di un video sintetico da localhost completati con configurazione di test isolata.
- Build PyInstaller creata in `dist-aggiornata/MovieDownloader`; avvio riuscito, finestra presente e processo responsivo. Aprire `Avvia aggiornato.bat` per questa build oppure `Avvia.bat` per il codice sorgente.


### Sfondo del film selezionato

- Il tema iniziale resta scuro. Selezionando una locandina, lo sfondo mostra l'immagine panoramica TMDb del titolo, sfocata e oscurata; la locandina è il fallback immediato.
- Caricamento asincrono con annullamento della richiesta precedente, cache in memoria limitata a otto immagini e nessuna modifica alle impostazioni persistenti. Immagini mancanti o errori di rete non bloccano la selezione né mostrano finestre di errore.
- 24 test passati, inclusi selezioni rapide, risposte tardive, fallback, cache, immagini non valide, contrasto delle immagini chiare e ridimensionamento.
- Ricerca e sfondo panoramico di The Batman verificati con TMDb. Build in `dist-aggiornata/sfondo-dinamico/MovieDownloader`; `Avvia aggiornato.bat` punta alla nuova versione.
- Redesign precedente pubblicato su `origin/main` nel commit `57db1c8`; le modifiche allo sfondo sono successive a quel push.


## Release 2.2.0 — 28 ottobre 2026

- Versione applicazione 2.2.0, ProductVersion Windows 2.2.0 e FileVersion 2.2.0.0.
- Build standalone a file singolo, ZIP distribuibile, release notes italiane e checksum SHA-256 in `dist-aggiornata/v2.2.0`.
- `CreaExe.bat` usa `scripts/build_release.py`; il numero di versione deriva da `config/version.py`. `Avvia aggiornato.bat` avvia la build 2.2.0.
- 28 test superati e smoke test locale completo riuscito. Controllo aggiornamenti corretto per non proporre downgrade.
- EXE standalone avviato: finestra presente e processo responsivo. Proprietà versione, integrità dello ZIP e checksum verificati.
- Note di rilascio in `releases/v2.2.0.md`; cronologia riassunta in `CHANGELOG.md`.
