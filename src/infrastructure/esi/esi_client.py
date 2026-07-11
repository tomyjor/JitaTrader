"""
Cliente ESI genérico, respetuoso con rate limits y con reintentos ante
errores transitorios (v1.1).
"""

import time
import requests
from typing import List, Dict, Optional


class ESIClient:
    BASE_URL = "https://esi.evetech.net/latest"
    DATASOURCE = "tranquility"

    #: Reintentos ante errores transitorios (timeouts, problemas de
    #: conexión, 5xx, o 420 "error limited" de ESI) antes de darse por
    #: vencido con ese request puntual. v1.1: antes, un único timeout o
    #: un 502 pasajero tiraba abajo el ítem entero en medio de un import
    #: masivo de cientos de ítems -- con imports de 100-400 ítems, la
    #: probabilidad de que ESI tenga al menos un hipo transitorio no es
    #: baja. Ahora se reintenta con backoff antes de reportarlo como
    #: fallo real (lo que sí sigue pasando si el error persiste).
    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 1.0
    RETRYABLE_STATUS_CODES = {420, 500, 502, 503, 504}

    def __init__(self, user_agent: str = "JitaTrader/2.0 (contact@tomas)", pool_size: int = 20):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json"
        })
        # Pool más grande para soportar imports masivos con descarga concurrente
        # (por default requests usa pool_maxsize=10, insuficiente si hacemos varios
        # workers en paralelo golpeando esi.evetech.net).
        adapter = requests.adapters.HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        self.session.mount("https://", adapter)

    def get(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """GET con manejo automático de paginación y reintentos ante fallos transitorios."""
        url = f"{self.BASE_URL}{endpoint}"
        params = dict(params or {})
        params["datasource"] = self.DATASOURCE

        all_data: List[Dict] = []
        page = 1

        while True:
            params["page"] = page
            response = self._get_with_retry(url, params)

            data = response.json()
            if not data:
                break

            all_data.extend(data)

            # Si hay header X-Pages, lo usamos
            pages = int(response.headers.get("X-Pages", 1))
            if page >= pages:
                break

            page += 1
            time.sleep(0.25)  # Respeto básico de rate limit

        return all_data

    def _get_with_retry(self, url: str, params: Dict) -> requests.Response:
        """
        Ejecuta un GET con reintentos ante errores transitorios (ver
        `MAX_RETRIES` / `RETRYABLE_STATUS_CODES`). Errores no transitorios
        (4xx que no sean 420, p.ej. un 404 por type_id inválido) se
        propagan de inmediato sin reintentar -- reintentar un error
        permanente solo demora el fallo, no lo evita.
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.get(url, params=params, timeout=30)
            except requests.exceptions.RequestException as e:
                last_error = e
            else:
                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response
                last_error = requests.exceptions.HTTPError(
                    f"{response.status_code} (transitorio) en {url}"
                )

            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_BACKOFF_SECONDS * attempt)

        assert last_error is not None
        raise last_error

    def close(self):
        self.session.close()
