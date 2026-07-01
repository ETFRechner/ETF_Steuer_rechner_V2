from datetime import date
from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator

# --- Enums ---
class RechenZiel(str, Enum):
    STEUERFREI = "steuerfrei"
    WUNSCHNETTO = "wunschnetto"
    ANTEILE = "anteile"

class KirchensteuerStatus(str, Enum):
    NEIN = "nein"
    ACHT_PROZENT = "8%"
    NEUN_PROZENT = "9%"

# --- Unter-Modelle ---
class KaufEintrag(BaseModel):
    datum: date
    anzahl: float
    preis: float

    @field_validator("anzahl", "preis", mode="before")
    @classmethod
    def bereinige_numerische_felder(cls, v):
        # Falls NaN oder ungültige Werte aus JS kommen, zu 0.0 machen
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

class VorabEintrag(BaseModel):
    jahr: int
    wert: float

    @field_validator("jahr", "wert", mode="before")
    @classmethod
    def bereinige_vorab(cls, v):
        try:
            return float(v) if "." in str(v) else int(v)
        except (ValueError, TypeError):
            return 0

# # --- Haupt-Payload ---
# class CalculationPayload(BaseModel):
#     rechen_ziel: RechenZiel
#     wert_wunschnetto: float = 0.0
#     wert_anteile: float = 0.0
#     verkaufskurs: float = 0.0
    
#     teilfreistellung: float = 0.0
#     ist_thesaurierend: bool = False
    
#     freibetrag: float = 0.0
#     verlusttopf: float = 0.0
#     kirchensteuer: KirchensteuerStatus
#     bereits_verkaufte_anteile: float = 0.0
#     tagesgenau: bool = False
#     manuelle_vorabpauschale_aktiv: bool = False
    
#     kaeufe: List[KaufEintrag] = Field(default_factory=list)
#     # 🎯 WICHTIG: Erlaubt nun explizit leere Listen ohne Absturz
#     vorabpauschalen: List[VorabEintrag] = Field(default_factory=list)
#     quelle: str
#     ticker: Optional[str] = None

#     # --- Vor-Validierer für maximale JS-Kompatibilität ---
    
#     @field_validator("wert_wunschnetto", "wert_anteile", "verkaufskurs", "teilfreistellung", "freibetrag", "verlusttopf", "bereits_verkaufte_anteile", mode="before")
#     @classmethod
#     def konvertiere_floats(cls, v):
#         if v is None or v == "" or str(v).lower() == "nan":
#             return 0.0
#         try:
#             return float(v)
#         except (ValueError, TypeError):
#             return 0.0

#     @field_validator("rechen_ziel", mode="before")
#     @classmethod
#     def bereinige_rechen_ziel(cls, v):
#         if isinstance(v, str):
#             return v.strip().lower()
#         return v

#     @field_validator("kirchensteuer", mode="before")
#     @classmethod
#     def bereinige_kirchensteuer(cls, v):
#         if isinstance(v, str):
#             v_clean = v.strip().lower()
#             if v_clean in ("0", "false", "nein", "keine", ""):
#                 return KirchensteuerStatus.NEIN
#             if "8" in v_clean:
#                 return KirchensteuerStatus.ACHT_PROZENT
#             if "9" in v_clean:
#                 return KirchensteuerStatus.NEUN_PROZENT
#         return v

#     # 🎯 AUTOMATISCHE PROZENT-KORREKTUR
#     @field_validator("teilfreistellung")
#     @classmethod
#     def korrigiere_prozentwert(cls, v):
#         # Wenn das Frontend z.B. 30 schickt (statt 0.30), rechnen wir es hier auf 0.30 um,
#         # da deine funktionen_api.py mit `payload.teilfreistellung * 0.01` arbeitet!
#         if v > 1.0:
#             return v
#         else:
#             # Falls das Frontend bereits 0.3 schickt, rechnest du in funktionen_api.py * 0.01.
#             # Um das einheitlich zu halten: Wir belassen den Wert so, wie er kommt, 
#             # entfernen aber harte Restriktionen (< 1.0) im Modell.
#             return v

# --- Haupt-Payload ---
class CalculationPayload(BaseModel):
    rechen_ziel: RechenZiel
    wert_wunschnetto: float = 0.0
    wert_anteile: float = 0.0
    verkaufskurs: float = 0.0
    
    teilfreistellung: float = 0.0
    ist_thesaurierend: bool = False
    
    freibetrag: float = 0.0
    verlusttopf: float = 0.0
    kirchensteuer: KirchensteuerStatus
    bereits_verkaufte_anteile: float = 0.0
    tagesgenau: bool = False
    manuelle_vorabpauschale_aktiv: bool = False
    
    kaeufe: List[KaufEintrag] = Field(default_factory=list)
    # 🎯 WICHTIG: Erlaubt nun explizit leere Listen ohne Absturz
    vorabpauschalen: List[VorabEintrag] = Field(default_factory=list)
    quelle: str
    ticker: Optional[str] = None

    # --- Vor-Validierer für maximale JS-Kompatibilität ---
    
    # 🎯 ERWEITERT: Fängt jetzt zuverlässig "NaN", "null", "undefined" und leere Werte bei Tabelleneingaben ab
    @field_validator(
        "wert_wunschnetto", 
        "wert_anteile", 
        "verkaufskurs", 
        "teilfreistellung", 
        "freibetrag", 
        "verlusttopf", 
        "bereits_verkaufte_anteile", 
        mode="before"
    )
    @classmethod
    def konvertiere_floats(cls, v):
        if v is None or v == "" or str(v).lower() in ("nan", "null", "undefined"):
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("rechen_ziel", mode="before")
    @classmethod
    def bereinige_rechen_ziel(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("kirchensteuer", mode="before")
    @classmethod
    def bereinige_kirchensteuer(cls, v):
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("0", "false", "nein", "keine", "", "null", "undefined"):
                return KirchensteuerStatus.NEIN
            if "8" in v_clean:
                return KirchensteuerStatus.ACHT_PROZENT
            if "9" in v_clean:
                return KirchensteuerStatus.NEUN_PROZENT
        return v

    # 🎯 AUTOMATISCHE PROZENT-KORREKTUR
    @field_validator("teilfreistellung")
    @classmethod
    def korrigiere_prozentwert(cls, v):
        # Wenn das Frontend z.B. 30 schickt (statt 0.30), rechnen wir es hier auf 0.30 um,
        # da deine funktionen_api.py mit `payload.teilfreistellung * 0.01` arbeitet!
        if v > 1.0:
            return v
        else:
            # Falls das Frontend bereits 0.3 schickt, rechnest du in funktionen_api.py * 0.01.
            # Um das einheitlich zu halten: Wir belassen den Wert so, wie er kommt, 
            # entfernen aber harte Restriktionen (< 1.0) im Modell.
            return v
        
class SparplanPayload(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    tag: int
    rate: float