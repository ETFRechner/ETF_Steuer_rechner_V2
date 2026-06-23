from pydantic import BaseModel
from typing import List
from datetime import date

# Ein einzelner Kauf aus der Tabelle
class KaufEintrag(BaseModel):
    datum: date
    anzahl: float
    preis: float

# Ein einzelner Eintrag aus der Vorabpauschalen-Tabelle
class VorabEintrag(BaseModel):
    jahr: int
    wert: float

# Das gesamte Paket, das vom "Berechnen"-Button gesendet wird
class CalculationPayload(BaseModel):
    rechen_ziel: str
    wert_wunschnetto: float
    wert_anteile: float
    verkaufskurs: float
    freibetrag: float
    verlusttopf: float
    kirchensteuer: str
    tagesgenau: bool
    kaeufe: List[KaufEintrag]
    vorabpauschalen: List[VorabEintrag]