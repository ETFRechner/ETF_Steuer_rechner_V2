from pydantic import BaseModel
from typing import List
from datetime import date
from typing import List, Optional

# Ein einzelner Kauf aus der Tabelle
class KaufEintrag(BaseModel):
    datum: date
    anzahl: float
    preis: float

# Ein einzelner Eintrag aus der Vorabpauschalen-Tabelle
class VorabEintrag(BaseModel):
    jahr: int
    wert: float

class CalculationPayload(BaseModel):
    rechen_ziel: str
    wert_wunschnetto: float
    wert_anteile: float
    verkaufskurs: float
    
    # HIER ERGÄNZEN:
    teilfreistellung: float
    ist_thesaurierend: bool
    
    freibetrag: float
    verlusttopf: float
    kirchensteuer: str
    bereits_verkaufte_anteile: float
    tagesgenau: bool
    manuelle_vorabpauschale_aktiv: bool = False
    kaeufe: List[KaufEintrag]
    vorabpauschalen: List[VorabEintrag]
    quelle: str
    ticker: Optional[str] = None

class SparplanPayload(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    tag: int
    rate: float