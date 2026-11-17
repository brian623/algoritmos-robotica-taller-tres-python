"""Convierte las consignas del SCARA en pulsos calibrados."""

BASE = ((0, 600), (90, 1800), (135, 2500))
CODO = ((0, 1970), (90, 740), (100, 600))
MARCADOR_ARRIBA = 800
MARCADOR_ABAJO = 1890


def interpolar(angulo, referencias, nombre):
    if not referencias[0][0] <= angulo <= referencias[-1][0]:
        raise ValueError(
            f"{nombre}: {angulo:.1f}° fuera del rango físico "
            f"{referencias[0][0]}–{referencias[-1][0]}°."
        )
    for (a, p), (b, q) in zip(referencias, referencias[1:]):
        if angulo <= b:
            return p + (q - p) * (angulo - a) / (b - a)


def pulsos_xy(q1, q2):
    return interpolar(q1, BASE, "Base"), interpolar(q2, CODO, "Codo")


class ControlScara:
    def __init__(self):
        import board
        from adafruit_pca9685 import PCA9685

        self.pca = PCA9685(board.I2C(), address=0x40)
        try:
            self.pca.frequency = 50
            self.frecuencia = self.pca.frequency
            for canal in range(3):
                self.pca.channels[canal].duty_cycle = 0
        except Exception:
            self.pca.deinit()
            raise

    def _pulso(self, canal, microsegundos):
        self.pca.channels[canal].duty_cycle = round(
            microsegundos * self.frecuencia * 65536 / 1_000_000
        )

    def mover(self, q1, q2):
        base, codo = pulsos_xy(q1, q2)
        self._pulso(0, base)
        self._pulso(1, codo)

    def marcador(self, arriba):
        self._pulso(2, MARCADOR_ARRIBA if arriba else MARCADOR_ABAJO)

    def cerrar(self):
        error = None
        for canal in range(3):
            try:
                self.pca.channels[canal].duty_cycle = 0
            except OSError as fallo:
                error = fallo
        self.pca.deinit()
        if error is not None:
            raise error
