"""Prueba un canal del PCA9685 con pulsos cerca del centro nominal."""

import argparse
from time import sleep


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "canal", type=int, choices=(0, 1, 2),
        help="0 = base, 1 = codo, 2 = marcador",
    )
    args = parser.parse_args()

    import board
    from adafruit_pca9685 import PCA9685

    with PCA9685(board.I2C(), address=0x40) as pca:
        canal = pca.channels[args.canal]
        try:
            pca.frequency = 50
            frecuencia = pca.frequency
            for pulso_us in (1500, 1450, 1550, 1500):
                print(f"Canal {args.canal}: {pulso_us} µs", flush=True)
                canal.duty_cycle = round(pulso_us * frecuencia * 65536 / 1_000_000)
                sleep(1)
        finally:
            canal.duty_cycle = 0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
