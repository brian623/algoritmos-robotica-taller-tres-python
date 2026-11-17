"""Letras de palo para escribir nombres con un marcador."""

from unicodedata import normalize

# Cada par de dígitos es un punto X/Y. La barra separa trazos.
LETRAS = {
    "A": "00 26 40/12 32",
    "B": "00 06 36 45 44 33 03/33 42 41 30 00",
    "C": "45 36 16 05 01 10 30 41",
    "D": "00 06 26 45 41 20 00",
    "E": "46 06 00 40/03 33",
    "F": "00 06 46/03 33",
    "G": "45 36 16 05 01 10 30 41 43 23",
    "H": "06 00/46 40/03 43",
    "I": "06 46/26 20/00 40",
    "J": "06 46/36 31 20 10 01",
    "K": "06 00/46 03 40",
    "L": "06 00 40",
    "M": "00 06 23 46 40",
    "N": "00 06 40 46",
    "O": "10 01 05 16 36 45 41 30 10",
    "P": "00 06 36 45 44 33 03",
    "Q": "10 01 05 16 36 45 41 30 10/22 40",
    "R": "00 06 36 45 44 33 03/23 40",
    "S": "45 36 16 05 04 13 33 42 41 30 10 01",
    "T": "06 46/26 20",
    "U": "06 01 10 30 41 46",
    "V": "06 20 46",
    "W": "06 10 23 30 46",
    "X": "06 40/46 00",
    "Y": "06 23 46/23 20",
    "Z": "06 46 00 40",
}
MARCAS = {"́": "27 38", "̃": "17 28 37 48", "̈": "17 18/37 38"}


def trazos_nombre(texto):
    """Genera trazos en mm, con X desde 150 y Y desde 100."""
    nombre = normalize("NFC", texto.strip())
    if not 6 <= len(nombre) <= 8:
        raise ValueError("Ingresa un nombre de 6 a 8 caracteres.")
    glifos = []
    for caracter in nombre:
        if caracter in " -":
            glifos.append("03 43" if caracter == "-" else "")
            continue
        base, *marcas = normalize("NFD", caracter.upper())
        if base not in LETRAS or any(marca not in MARCAS for marca in marcas):
            raise ValueError("Usa letras, espacios o guiones. Se admiten tildes, ñ y ü.")
        glifos.append("/".join([LETRAS[base], *(MARCAS[m] for m in marcas)]))
    if not any(c.isalpha() for c in nombre):
        raise ValueError("El nombre debe contener letras.")

    trazos = []
    for i, glifo in enumerate(glifos):
        for trazo in filter(None, glifo.split("/")):
            trazos.append([
                (150 + 9 * i + 1.75 * int(x), 100 + 2.5 * int(y))
                for x, y in trazo.split()
            ])
    return nombre.upper(), trazos
