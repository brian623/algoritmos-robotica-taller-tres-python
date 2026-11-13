# Pruebas del SCARA en la Raspberry Pi 4B

## Actualizar el proyecto

Abre una terminal en la carpeta donde clonaste el repositorio y ejecuta:

```bash
git pull --ff-only
```

## Habilitar y comprobar I²C

Haz esta configuración una vez en Raspberry Pi OS:

```bash
sudo raspi-config
```

Activa **Interface Options → I2C** y sal. Si el asistente pide reiniciar, hazlo antes de continuar. Instala las herramientas y escanea el bus:

```bash
sudo apt update
sudo apt install i2c-tools python3-venv libgpiod-dev python3-libgpiod
i2cdetect -y 1
```

Debe aparecer `40` en la tabla si el PCA9685 tiene la dirección de fábrica (`0x40`). Si no aparece, revisa SDA, SCL, VCC y GND. Si el escaneo indica un error de permisos, repítelo con `sudo i2cdetect -y 1`. [Configuración de I²C](https://www.raspberrypi.com/documentation/computers/configuration.html) · [Detección del PCA9685](https://learn.adafruit.com/adafruit-16-channel-servo-driver-with-raspberry-pi/overview)

## Preparar el entorno Python

Crea el entorno e instala el controlador una sola vez:

```bash
python3 -m venv --system-site-packages ~/.venv-scara
source ~/.venv-scara/bin/activate
python -m pip install adafruit-blinka adafruit-circuitpython-pca9685
```

En cada terminal nueva, activa el entorno con `source ~/.venv-scara/bin/activate`. [Instalación de Blinka](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux?view=all)

## Probar los servos

Para la primera prueba, conecta solo el servo que vas a probar. Apaga la alimentación de los servos antes de cambiar conectores. Deja libre el eje del servo, especialmente el piñón del SG90. El primer pulso lleva el servo desde su posición actual al centro nominal.

Desde la carpeta del proyecto, ejecuta una línea a la vez y observa el movimiento:

```bash
python probar_pca9685.py 0  # MG90S de la base
python probar_pca9685.py 1  # MG90S del codo
python probar_pca9685.py 2  # SG90 del marcador
```

Cada prueba aplica pulsos de 1500, 1450, 1550 y 1500 µs a 50 Hz. El servo se centra, se mueve un poco hacia ambos lados y vuelve al centro. Si llega a un tope o zumba sin moverse, interrumpe con **Ctrl+C**. El script desactiva la señal del canal al salir, incluida la interrupción por teclado. Estas pruebas verifican el movimiento. Los ceros, sentidos de giro y límites se determinan durante la calibración. [Control PWM del PCA9685](https://learn.adafruit.com/16-channel-pwm-servo-driver/python-circuitpython)

## Abrir la simulación

Desde una terminal del escritorio de la Raspberry, en la carpeta del proyecto:

```bash
python3 gui_scara.py
```

Si falta Tkinter, instálalo con `sudo apt install python3-tk`. La GUI ejecuta la simulación. El movimiento de los servos se prueba con el script de terminal.

## Calibrar los servos

Conecta un servo a la vez y activa el entorno. El primer pulso es el centro nominal de 1500 µs. Antes de activarlo, libera el mecanismo si desconoces la posición que tomará.

```bash
source ~/.venv-scara/bin/activate
python calibrar_pca9685.py 0  # base
python calibrar_pca9685.py 1  # codo
python calibrar_pca9685.py 2  # marcador
```

Ejecuta una línea a la vez. Escribe **+** o **-** y pulsa Enter para variar 10 µs. Anota el pulso con el servo todavía activo. Sal con **q** o **Ctrl+C** para cortar su señal. Si el mecanismo llega a un tope o se traba, corta la señal de inmediato. Los límites iniciales de 1400 a 1600 µs son para explorar cerca del centro. Puedes ampliar la ventana con **--minimo** y **--maximo** de forma gradual, manteniendo el recorrido libre. Usa **--inicio** para retomar desde un pulso ya comprobado.

| Canal | Posiciones a medir |
|---|---|
| 0 · Base | Usa +X como referencia de 0°. Mide el ángulo del primer eslabón en sentido antihorario desde arriba. Anota pares ángulo/pulso en el centro y cerca de ambos extremos útiles. |
| 1 · Codo | Con ambos eslabones alineados y extendidos, el ángulo relativo es 0°. Mide el giro del segundo eslabón respecto al primero en sentido horario desde arriba. Anota pares ángulo/pulso en el centro y cerca de ambos extremos útiles. |
| 2 · Marcador | Anota el pulso con la punta arriba y el pulso donde apenas toca el papel. |

Registra el ángulo realmente alcanzado. Si el montaje no llega a 0° o 180°, anota el límite medido sin forzarlo.
