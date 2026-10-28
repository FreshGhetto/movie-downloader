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
