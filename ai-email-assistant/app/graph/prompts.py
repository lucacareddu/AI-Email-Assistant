SUMMARIZE_PROMPT = """Sei un assistente che riassume email in arrivo per un team di supporto.
Riassumi in massimo 2 frasi il contenuto dell'email seguente, mantenendo solo i fatti rilevanti.

Oggetto: {subject}
Corpo:
{body}

Rispondi solo con il riassunto, senza preamboli."""


CLASSIFY_PROMPT = """Classifica l'email seguente in UNA sola di queste categorie:
support, sales, billing, other.

Oggetto: {subject}
Riassunto: {summary}

Rispondi solo con il nome della categoria, in minuscolo, senza altro testo."""


GENERATE_PROMPT = """Sei l'assistente email di un'azienda. Scrivi una risposta professionale,
chiara e concisa all'email del cliente, basandoti sul contesto recuperato dalla documentazione
aziendale quando è utile. Se il contesto non è rilevante, ignoralo.

Email del cliente (oggetto: {subject}):
{body}

Categoria: {category}

Contesto recuperato dalla documentazione aziendale:
{context}

{revision_note}

Scrivi solo il corpo della risposta email, senza oggetto e senza firma."""


REVIEW_PROMPT = """Valuta la bozza di risposta email seguente su una scala da 1 a 10,
considerando tono professionale, pertinenza rispetto alla richiesta e chiarezza.

Email originale:
{body}

Bozza di risposta:
{draft}

Rispondi SOLO con un JSON in questo formato esatto, senza altro testo:
{{"score": <numero intero 1-10>, "notes": "<una frase con eventuali correzioni da fare>"}}"""
