"""Ajusta un servo del SCARA en pasos de 10 µs."""

import argparse

PASO_US = 10


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canal", type=int, choices=(0, 1, 2))
    parser.add_argument("--inicio", type=int, default=1500)
    parser.add_argument("--minimo", type=int, default=1400)
    parser.add_argument("--maximo", type=int, default=1600)
    args = parser.parse_args()
    if not 500 <= args.minimo <= args.inicio <= args.maximo <= 2500:
        parser.error("Usa 500 <= mínimo <= inicio <= máximo <= 2500 µs.")

    import board
    from adafruit_pca9685 import PCA9685

    pulso = args.inicio
    print("Prueba un solo servo. Mantén libre su recorrido.")
    input(f"Pulsa Enter para activar el canal {args.canal} a {pulso} µs: ")
    with PCA9685(board.I2C(), address=0x40) as pca:
        canal = pca.channels[args.canal]
        try:
            pca.frequency = 50
            frecuencia = pca.frequency
            while True:
                canal.duty_cycle = round(pulso * frecuencia * 65536 / 1_000_000)
                while True:
                    orden = input(f"{pulso} µs [+ / - / q para salir]: ").strip().lower()
                    if orden == "q":
                        return
                    if orden not in ("+", "-"):
                        continue
                    siguiente = pulso + (PASO_US if orden == "+" else -PASO_US)
                    if args.minimo <= siguiente <= args.maximo:
                        pulso = siguiente
                        break
                    print("Límite de esta sesión alcanzado.")
        finally:
            canal.duty_cycle = 0


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130)
