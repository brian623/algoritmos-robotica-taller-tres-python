"""Cinemática nominal del SCARA del Taller 3, en milímetros y grados."""

from dataclasses import dataclass
from math import acos, atan2, cos, degrees, isfinite, radians, sin

TOLERANCIA = 1e-8


@dataclass(frozen=True)
class Scara:
    """L1 y L2 estimados entre ejes en el plano de ensamble."""

    l1: float = 139.0
    l2: float = 124.0

    def __post_init__(self) -> None:
        if not all(isfinite(l) and l > 0 for l in (self.l1, self.l2)):
            raise ValueError("Las longitudes deben ser positivas y finitas.")

    def directa(self, q1: float, q2: float) -> tuple[float, float]:
        """q1 gira en sentido antihorario y q2 en sentido horario (Figura 2)."""
        if not (0 <= q1 <= 180 and 0 <= q2 <= 180):
            raise ValueError("Los ángulos deben estar entre 0° y 180°.")
        base = radians(q1)
        punta = radians(q1 - q2)
        return (
            self.l1 * cos(base) + self.l2 * cos(punta),
            self.l1 * sin(base) + self.l2 * sin(punta),
        )

    def inversa(self, x: float, y: float) -> tuple[float, float]:
        """Devuelve la solución codo abajo dentro de los límites nominales."""
        if not (isfinite(x) and isfinite(y)):
            raise ValueError("Las coordenadas deben ser finitas.")
        cos_codo = (x*x + y*y - self.l1**2 - self.l2**2) / (2*self.l1*self.l2)
        if not -1 - TOLERANCIA <= cos_codo <= 1 + TOLERANCIA:
            raise ValueError("El punto queda fuera del área de trabajo.")

        # En el origen, dos eslabones iguales plegados admiten cualquier q1.
        if x == 0 and y == 0 and self.l1 == self.l2:
            return 0.0, 180.0

        if abs(abs(cos_codo) - 1.0) < 1e-14:
            cos_codo = 1.0 if cos_codo > 0 else -1.0
        codo = acos(max(-1.0, min(1.0, cos_codo)))
        giro = atan2(-self.l2 * sin(codo), self.l1 + self.l2 * cos(codo))
        q1 = degrees(atan2(y, x) - giro) % 360
        if q1 >= 360 - TOLERANCIA:
            q1 = 0.0
        if not -TOLERANCIA <= q1 <= 180 + TOLERANCIA:
            raise ValueError("El punto queda fuera del área de trabajo en codo abajo.")
        return max(0.0, min(180.0, q1)), degrees(codo)

    def contorno(self, segmentos_por_arco: int = 90) -> list[tuple[float, float]]:
        """Muestrea el perímetro cerrado nominal para L1 mayor que L2."""
        if self.l1 <= self.l2:
            raise ValueError("Este contorno requiere L1 mayor que L2.")
        if segmentos_por_arco < 2:
            raise ValueError("Cada arco necesita al menos dos segmentos.")

        puntos = []
        for i in range(segmentos_por_arco):
            puntos.append(self.directa(180 * i / segmentos_por_arco, 0))
        for i in range(segmentos_por_arco):
            puntos.append(self.directa(180, 180 * i / segmentos_por_arco))
        for i in range(segmentos_por_arco):
            puntos.append(self.directa(180 - 180 * i / segmentos_por_arco, 180))
        for i in range(segmentos_por_arco):
            puntos.append(self.directa(0, 180 - 180 * i / segmentos_por_arco))
        return puntos + [puntos[0]]
