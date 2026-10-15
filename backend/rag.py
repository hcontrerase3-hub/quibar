"""Recuperación local y respuestas compuestas exclusivamente con datos aprobados."""

import re
import unicodedata

CATEGORIES = [
    ("Alojamiento", r"aloj|dorm|caban|camp|hosped|estad"),
    ("Gastronomía", r"comer|comida|almorz|restaur|cafe|desayun|pastel|once|hambre"),
    ("Artesanía", r"artesan|regalo|tejid|recuerdo|souvenir"),
    ("Turismo", r"pase|tour|turis|sender|camin|trek|excurs|aventur"),
    ("Comercio", r"tienda|compr|almacen|abarrot|mercad"),
]
STOP = {"quiero", "busco", "para", "algo", "donde", "puedo", "hay", "tienen", "tiene", "esta",
        "tomar", "tomarme", "beber", "beberme", "gustaria", "quisiera", "podria",
        "hoy", "aqui", "sobre", "lugar", "lugares", "opciones", "santa", "barbara", "quilaco",
        "comer", "comida", "alojamiento", "cabanas", "artesania", "turismo", "regalo",
        "pasear", "comprar", "horario", "hora", "cuando", "abre", "cierran", "atienden", "ofrece",
        "direccion", "ubicacion", "conocer", "recomienda", "necesito", "dame", "unos", "unas",
        "ideas", "rico", "rica", "alojarme", "hospedarme", "hecho", "mano", "cerca", "quieres",
        "negocio", "empresa", "cuales", "puedes", "opcion", "hacer", "encuentro", "informacion"}
NAMED = re.compile(r"\b(existe|conoces|hablame de|cuentame de|tienen registrado|busco el negocio|busco la empresa)\b")
FOLLOWUP = re.compile(r"\b(y su|y sus|de ese|de esa|ese lugar|esa opcion|su horario|a que hora|que ofrece|donde queda)\b")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def category_of(query: str) -> str | None:
    q = normalize(query)
    return next((category for category, pattern in CATEGORIES if re.search(pattern, q)), None)


def retrieve(query: str, rows: list[dict], context_ids: list[str] | None = None) -> list[dict]:
    """No recupera negocios suspendidos, ni inventa candidatos ante nombres desconocidos."""
    rows = [r for r in rows if r["status"] == "Aprobado"]
    q = normalize(query)
    named = [r for r in rows if normalize(r["name"]) in q]
    if named:
        return named[:3]
    if NAMED.search(q):
        return []
    if context_ids and FOLLOWUP.search(q):
        by_id = {r["id"]: r for r in rows}
        contextual = [by_id[i] for i in context_ids if i in by_id]
        if contextual:
            return contextual[:3]

    category = category_of(q)
    commune = "Santa Bárbara" if "santa barbara" in q else "Quilaco" if "quilaco" in q else None
    tokens = [w for w in re.findall(r"[a-z0-9]+", q) if len(w) > 3 and w not in STOP]
    candidates = []
    for row in rows:
        if commune and row["commune"] != commune:
            continue
        if category and row["category"] != category:
            continue
        haystack = normalize(" ".join([row["name"], row["category"], row["summary"],
                                   *row["offerings"], row["keywords"]]))
        matches = sum(word in haystack for word in tokens)
        # Un detalle pedido (p. ej. pizza) debe existir en la ficha; el rubro solo no basta.
        if tokens and matches != len(tokens):
            continue
        score = matches * 3 + (4 if category else 0) + (1 if commune else 0)
        if score or (commune and not tokens):
            candidates.append((score, row))
    return [row for _, row in sorted(candidates, key=lambda pair: (-pair[0], pair[1]["name"]))[:3]]


def intent_of(query: str) -> str:
    q = normalize(query)
    if re.search(r"horario|a que hora|cuando abre|cuando cierra|atiende", q):
        return "hours"
    if re.search(r"donde|direccion|ubicacion|queda", q):
        return "location"
    if re.search(r"ofrece|servicio|producto|que tiene", q):
        return "offerings"
    return "recommend"


def compose(rows: list[dict], intent: str, *, unknown: bool = False) -> str:
    if unknown or not rows:
        return "No cuento con ese registro en el catálogo de ejemplo aprobado. Puedes probar otra búsqueda o explorar las fichas disponibles."
    if len(rows) == 1:
        row = rows[0]
        prefix = f"En este catálogo de ejemplo, {row['name']}"
        if intent == "hours":
            return f"{prefix} indica este horario: {row['hours']}. Abre la ficha para revisar el dato completo."
        if intent == "location":
            return f"{prefix} figura en {row['area']}, {row['commune']}."
        if intent == "offerings":
            return f"{prefix} ofrece: {', '.join(row['offerings'])}."
        return f"{prefix} aparece en {row['commune']}: {row['summary']}"
    names = ", ".join(r["name"] for r in rows)
    return f"Encontré estas opciones aprobadas en el catálogo de ejemplo: {names}. Toca una ficha para ver sus datos."
