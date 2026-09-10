SUMMARIZE_AND_CLASSIFY_PROMPT = """Sei un assistente che analizza email in arrivo per un team di supporto.

Oggetto: {subject}
Corpo:
{body}

Fai due cose:
1. Riassumi in massimo 2 frasi il contenuto dell'email, mantenendo solo i fatti rilevanti.
2. Classifica l'email in UNA sola di queste categorie: support, sales, billing, other."""

# Gemini structured output - constrains the model to this exact shape.
SUMMARIZE_AND_CLASSIFY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "category": {
            "type": "STRING",
            "enum": ["support", "sales", "billing", "other"],
        },
    },
    "required": ["summary", "category"],
}


GENERATE_PROMPT = """Sei l'assistente email di un'azienda. Scrivi una risposta professionale,
chiara e concisa all'email del cliente, basandoti sul contesto recuperato dalla documentazione
aziendale quando è utile. Se il contesto non è rilevante, ignoralo.

Email del cliente (oggetto: {subject}):
{body}

Categoria: {category}

Contesto recuperato dalla documentazione aziendale:
{context}

Memoria di email precedenti ricevute da questo stesso mittente (ignora se non rilevante):
{sender_memory}

Scrivi solo il corpo della risposta email, senza oggetto e senza firma."""


REVISE_PROMPT = """Sei l'assistente email di un'azienda. Hai già scritto una bozza di risposta
all'email del cliente; ora devi rivederla seguendo le indicazioni del revisore.

Email del cliente (oggetto: {subject}):
{body}

Categoria: {category}

Contesto recuperato dalla documentazione aziendale:
{context}

Memoria di email precedenti ricevute da questo stesso mittente (ignora se non rilevante):
{sender_memory}

Bozza precedente da correggere:
{previous_draft}

=== INDICAZIONI DEL REVISORE (hanno la priorità: applicale tutte) ===
{review_notes}
=== FINE INDICAZIONI DEL REVISORE ===

Riscrivi la bozza applicando le indicazioni qui sopra, conservando ciò che già va bene.
Scrivi solo il corpo della risposta email, senza oggetto e senza firma."""


REVIEW_PROMPT = """Valuta la bozza di risposta email seguente su una scala da 1 a 10,
considerando tono professionale, pertinenza rispetto alla richiesta e chiarezza.

Email originale:
{body}

Bozza di risposta:
{draft}

Rispondi SOLO con un JSON in questo formato esatto, senza altro testo:
{{"score": <numero intero 1-10>, "notes": "<una frase con eventuali correzioni da fare>"}}"""
