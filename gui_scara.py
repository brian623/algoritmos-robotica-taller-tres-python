"""Posicionamiento y simulación visual del SCARA del Taller 3."""

import argparse
import tkinter as tk
from dataclasses import dataclass
from math import ceil, cos, hypot, radians, sin, tau
from pathlib import Path
from time import monotonic
from tkinter import messagebox, ttk
from xml.etree import ElementTree

from cinematica import Scara
from control_scara import ControlScara, pulsos_xy


@dataclass(frozen=True)
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0

    def transformar(self, punto):
        x, y, z = punto
        return (
            self.x + cos(self.yaw) * x - sin(self.yaw) * y,
            self.y + sin(self.yaw) * x + cos(self.yaw) * y,
            self.z + z,
        )


def vector(nodo, atributo="xyz"):
    return tuple(map(float, nodo.attrib[atributo].split()))


class ModeloUrdf:
    """Lee la cadena del SCARA, con cajas y articulaciones sobre el eje Z."""

    def __init__(self, archivo):
        robot = ElementTree.parse(archivo).getroot()
        self.cajas = {}
        self.articulaciones = {}
        for enlace in robot.findall("link"):
            visual = enlace.find("visual")
            if visual is not None:
                centro = vector(visual.find("origin"))
                tamaño = vector(visual.find("geometry/box"), "size")
                rgb = vector(visual.find("material/color"), "rgba")[:3]
                color = "#" + "".join(f"{round(c * 255):02x}" for c in rgb)
                self.cajas[enlace.attrib["name"]] = (centro, tamaño, color)

        for joint in robot.findall("joint"):
            nombre = joint.attrib["name"]
            tipo = joint.attrib["type"]
            padre = joint.find("parent").attrib["link"]
            hijo = joint.find("child").attrib["link"]
            origen = vector(joint.find("origin"))
            eje = vector(joint.find("axis")) if tipo != "fixed" else (0, 0, 1)
            if eje not in ((0, 0, 1), (0, 0, -1)):
                raise ValueError(f"El eje de {nombre} debe ser vertical.")
            self.articulaciones[nombre] = (tipo, padre, hijo, origen, eje[2])
            if nombre == "marcador_z":
                limite = joint.find("limit")
                self.z_arriba = float(limite.attrib["lower"])
                self.z_abajo = float(limite.attrib["upper"])

        self.cinematica = Scara(
            self.articulaciones["codo_giro"][3][0] * 1000,
            self.articulaciones["marcador_z"][3][0] * 1000,
        )

    def poses(self, q1, q2, z):
        mandos = {"base_giro": radians(q1), "codo_giro": radians(q2), "marcador_z": z}
        poses = {"base": Pose()}
        for nombre, (tipo, padre, hijo, origen, signo) in self.articulaciones.items():
            pose_padre = poses[padre]
            x, y, altura = pose_padre.transformar(origen)
            yaw = pose_padre.yaw
            if tipo == "revolute":
                yaw += signo * mandos[nombre]
            elif tipo == "prismatic":
                altura += signo * mandos[nombre]
            poses[hijo] = Pose(x, y, altura, yaw)
        return poses


def proyectar(punto):
    """Proyección ortográfica. La tercera coordenada se usa para ordenar caras."""
    x, y, z = punto
    horizontal = 0.94 * x - 0.34 * y
    profundidad = 0.34 * x + 0.94 * y
    return horizontal, -0.6 * profundidad - 0.8 * z, 0.8 * profundidad - 0.6 * z


def caras_de_caja(pose, centro, tamaño):
    vertices = [
        pose.transformar(tuple(c + s * d / 2 for c, s, d in zip(centro, signos, tamaño)))
        for signos in (
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        )
    ]
    for indices in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
                    (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        yield [vertices[i] for i in indices]


class Aplicacion:
    def __init__(self, ventana, modelo, control=None, inicial=None):
        self.ventana = ventana
        self.modelo = modelo
        self.control = control
        self.fallo = False
        self.q = inicial if inicial is not None else modelo.cinematica.inversa(160, 100)
        self.z = modelo.z_arriba
        self.objetivo = modelo.cinematica.directa(*self.q)
        self.punta_lista = monotonic() + 1 if control else 0
        self.animacion = None
        self.trazando = False
        self.trazo = []
        self.contorno = [(x / 1000, y / 1000, 0) for x, y in modelo.cinematica.contorno()]

        modo = "Robot físico" if control else "Simulación"
        ventana.title(f"Taller 3 · SCARA · {modo}")
        ventana.protocol("WM_DELETE_WINDOW", self.cerrar)
        ventana.minsize(640, 480)
        ventana.columnconfigure(0, weight=1)
        ventana.rowconfigure(1, weight=1)
        controles = ttk.Frame(ventana, padding=12)
        controles.grid(row=0, column=0, sticky="ew")
        self.x = tk.StringVar(value=f"{self.objetivo[0]:.3f}" if control else "160")
        self.y = tk.StringVar(value=f"{self.objetivo[1]:.3f}" if control else "100")
        for columna, (etiqueta, variable) in enumerate((("X (mm)", self.x), ("Y (mm)", self.y))):
            ttk.Label(controles, text=etiqueta).grid(row=0, column=2 * columna, padx=(0, 5))
            entrada = ttk.Entry(controles, textvariable=variable, width=9)
            entrada.grid(row=0, column=2 * columna + 1, padx=(0, 12))
            entrada.bind("<Return>", lambda _: self.mover())
        ttk.Button(controles, text="Mover manualmente", command=self.mover).grid(row=0, column=4)
        ttk.Button(controles, text="Subir / bajar punta", command=self.cambiar_altura).grid(
            row=0, column=5, padx=(8, 0)
        )
        ttk.Button(controles, text="Trazar Nike", command=self.trazar_nike).grid(
            row=1, column=4, sticky="e", pady=(9, 0)
        )
        ttk.Button(controles, text="Trazar Capitán América", command=self.trazar_escudo).grid(
            row=1, column=5, sticky="e", padx=(8, 0), pady=(9, 0)
        )
        self.modo_trazo = tk.StringVar(value="Por pasos (2 mm)")
        ttk.Combobox(
            controles, textvariable=self.modo_trazo, state="readonly", width=19,
            values=("Normal", "Media velocidad", "Por pasos (2 mm)"),
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(9, 0))
        self.angulos = tk.StringVar()
        ttk.Label(controles, textvariable=self.angulos).grid(
            row=2, column=0, columnspan=6, sticky="w", pady=(9, 0)
        )
        self.lienzo = tk.Canvas(ventana, bg="#f5f8fa", highlightthickness=0, width=760, height=470)
        self.lienzo.grid(row=1, column=0, sticky="nsew", padx=12)
        self.lienzo.bind("<Configure>", lambda _: self.dibujar())
        mensaje = (
            "Punta arriba. Ingresa un punto dentro del rango físico."
            if control else "Simulación URDF. Ingresa un punto dentro del contorno."
        )
        self.estado = tk.StringVar(value=mensaje)
        ttk.Label(ventana, textvariable=self.estado, padding=12).grid(row=2, column=0, sticky="ew")

    def enviar(self, accion, *argumentos):
        try:
            accion(*argumentos)
            return True
        except OSError as error:
            self.fallo = True
            try:
                self.control.cerrar()
            except OSError:
                pass
            self.control = None
            self.estado.set(f"Error I²C: {error}. Reinicia la aplicación para reconectar.")
            return False

    def cerrar(self):
        if self.animacion is not None:
            self.ventana.after_cancel(self.animacion)
        if self.control:
            try:
                self.control.cerrar()
            except OSError as error:
                messagebox.showerror("Error I²C", f"No se pudo cortar la señal PWM: {error}")
        self.ventana.destroy()

    def mover(self):
        if self.fallo or self.trazando:
            return
        try:
            x, y = (float(campo.get().replace(",", ".")) for campo in (self.x, self.y))
        except ValueError:
            self.estado.set("Ingresa números válidos para X e Y.")
            return
        try:
            destino = self.modelo.cinematica.inversa(x, y)
            if self.control:
                pulsos_xy(*destino)
        except ValueError as error:
            self.estado.set(str(error))
            return

        if self.animacion is not None:
            self.ventana.after_cancel(self.animacion)
        self.animacion = None
        self.objetivo = (x, y)
        if self.control and self.z != self.modelo.z_arriba:
            if not self.enviar(self.control.marcador, True):
                return
            self.punta_lista = monotonic() + 1
        self.z = self.modelo.z_arriba
        self.estado.set(f"Moviendo a ({x:g}, {y:g}) mm.")
        origen = self.q
        inicio = max(monotonic(), self.punta_lista)
        velocidad = 25 if self.control else 120
        duracion = max(abs(a - b) for a, b in zip(origen, destino)) / velocidad

        def avanzar():
            fraccion = min(1.0, max(0.0, (monotonic() - inicio) / duracion)) if duracion else 1.0
            posicion = destino if fraccion == 1 else tuple(
                (1 - fraccion) * a + fraccion * b for a, b in zip(origen, destino)
            )
            if self.control and not self.enviar(self.control.mover, *posicion):
                self.animacion = None
                return
            self.q = posicion
            self.dibujar()
            if fraccion < 1:
                self.animacion = self.ventana.after(25, avanzar)
            else:
                self.animacion = None
                resultado = "Consigna enviada" if self.control else "Punto alcanzado en simulación"
                self.estado.set(f"{resultado}: ({x:g}, {y:g}) mm.")

        espera_ms = max(0, round((inicio - monotonic()) * 1000))
        if espera_ms:
            self.animacion = self.ventana.after(espera_ms, avanzar)
        else:
            avanzar()

    def trazar_nike(self):
        # Contorno aproximado de la figura de la guía.
        silueta = (
            (1.00, 0.96), (0.40, 0.16), (0.30, 0.05), (0.22, 0.01),
            (0.15, 0.01), (0.09, 0.06), (0.05, 0.15), (0.02, 0.29),
            (0.01, 0.44), (0.02, 0.57), (0.05, 0.70), (0.09, 0.83),
            (0.16, 0.97), (0.13, 0.79), (0.12, 0.65), (0.13, 0.54),
            (0.17, 0.45), (0.23, 0.42), (0.30, 0.45), (1.00, 0.96),
        )
        vertices = [(150 + 70 * x, 100 + 27 * y) for x, y in silueta]
        self.trazar_logo("Nike", [vertices], "X 150–220 mm, Y 100–127 mm")

    def trazar_escudo(self):
        centro_x, centro_y = 183, 115
        trazos = []
        for radio in (30, 23, 16):
            trazos.append([
                (centro_x + radio * cos(tau * i / 100),
                 centro_y + radio * sin(tau * i / 100))
                for i in range(100)
            ])
        trazos.append([
            (centro_x + (14 if i % 2 == 0 else 5.5) * cos(tau * (0.25 + i / 10)),
             centro_y + (14 if i % 2 == 0 else 5.5) * sin(tau * (0.25 + i / 10)))
            for i in range(10)
        ])
        self.trazar_logo("Capitán América", trazos, "X 153–213 mm, Y 85–145 mm")

    def trazar_logo(self, nombre, contornos, zona):
        if self.fallo or self.animacion is not None:
            return
        modo = self.modo_trazo.get()
        por_pasos = modo == "Por pasos (2 mm)"
        paso_mm = 2 if por_pasos else 0.5
        trayectorias = []
        try:
            for vertices in contornos:
                if vertices[-1] != vertices[0]:
                    vertices = [*vertices, vertices[0]]
                puntos = vertices[:1]
                for (x, y), (u, v) in zip(vertices, vertices[1:]):
                    divisiones = max(1, ceil(hypot(u - x, v - y) / paso_mm))
                    puntos.extend(
                        (x + (u - x) * i / divisiones, y + (v - y) * i / divisiones)
                        for i in range(1, divisiones)
                    )
                    puntos.append((u, v))
                angulos = [self.modelo.cinematica.inversa(*punto) for punto in puntos]
                if self.control:
                    for pose in angulos:
                        pulsos_xy(*pose)
                trayectorias.append(list(zip(angulos, puntos)))
        except ValueError as error:
            self.estado.set(str(error))
            return
        if self.control and not messagebox.askokcancel(
            f"Trazar {nombre}", f"Fija la hoja bajo la zona {zona} y confirma.",
            parent=self.ventana,
        ):
            return

        self.trazando = True
        self.trazo.clear()
        self.estado.set(f"Trazando {nombre} · {modo}.")
        pausa = 1000 if self.control else 150
        intervalo = 50 if self.control else 15
        intervalo_trazo = intervalo * (2 if modo == "Media velocidad" else 1)
        if por_pasos:
            intervalo_trazo = 300
        def secuencia():
            yield True, None, pausa
            for trayectoria in trayectorias:
                origen = self.q
                destino = trayectoria[0][0]
                cambio = max(abs(a - b) for a, b in zip(origen, destino))
                pasos = max(1, ceil(cambio / 1.25))
                for i in range(1, pasos):
                    t = i / pasos
                    pose = tuple((1 - t) * a + t * b for a, b in zip(origen, destino))
                    yield pose, None, intervalo
                yield destino, None, pausa
                yield False, None, pausa
                for pose, punto in trayectoria:
                    yield pose, punto, intervalo_trazo
                yield None, None, pausa
                yield True, None, pausa

        acciones = iter(secuencia())

        def avanzar():
            self.animacion = None
            paso = next(acciones, None)
            if paso is None:
                self.trazando = False
                self.estado.set(f"{nombre} terminado. Marcador arriba.")
                return
            orden, punto, demora = paso
            if isinstance(orden, bool):
                if self.control and not self.enviar(self.control.marcador, orden):
                    self.trazando = False
                    return
                self.z = self.modelo.z_arriba if orden else self.modelo.z_abajo
                if not orden:
                    self.trazo.append([])
            elif orden is not None:
                if self.control and not self.enviar(self.control.mover, *orden):
                    self.trazando = False
                    return
                self.q = orden
                self.objetivo = self.modelo.cinematica.directa(*orden)
                if punto is not None:
                    self.trazo[-1].append(punto)
            self.dibujar()
            self.animacion = self.ventana.after(demora, avanzar)

        avanzar()

    def cambiar_altura(self):
        if self.fallo:
            return
        if self.animacion is not None or monotonic() < self.punta_lista:
            self.estado.set("Espera a que termine el movimiento X/Y.")
            return
        arriba = self.z != self.modelo.z_arriba
        if self.control and not self.enviar(self.control.marcador, arriba):
            return
        if self.control:
            self.punta_lista = monotonic() + 1
        self.z = self.modelo.z_arriba if arriba else self.modelo.z_abajo
        self.dibujar()

    def dibujar(self):
        ancho = self.lienzo.winfo_width()
        alto = self.lienzo.winfo_height()
        self.lienzo.delete("all")
        if ancho < 2 or alto < 2:
            return

        radio = (self.modelo.cinematica.l1 + self.modelo.cinematica.l2) / 1000
        escala = min((ancho - 44) / (2.2 * radio), (alto - 44) / (1.55 * radio))

        def pantalla(punto):
            u, v, _ = proyectar(punto)
            return ancho / 2 + u * escala, alto * 0.53 + v * escala

        self.lienzo.create_line(
            [coord for punto in self.contorno for coord in pantalla(punto)],
            fill="#627687", dash=(5, 4), width=2,
        )
        for trazo in self.trazo:
            if len(trazo) >= 2:
                self.lienzo.create_line(
                    [coord for x, y in trazo for coord in pantalla((x / 1000, y / 1000, 0))],
                    fill="#a14816", width=3,
                )
        for punto, etiqueta in (((radio, 0, 0), "+X"), ((0, radio, 0), "+Y")):
            self.lienzo.create_line(*pantalla((0, 0, 0)), *pantalla(punto), fill="#8292a0", arrow=tk.LAST)
            self.lienzo.create_text(*pantalla(punto), text=etiqueta, fill="#455565", anchor="sw")

        x, y = (valor / 1000 for valor in self.objetivo)
        u, v = pantalla((x, y, 0))
        self.lienzo.create_oval(u - 5, v - 5, u + 5, v + 5, outline="#a14816", width=2)
        poses = self.modelo.poses(*self.q, self.z)
        caras = []
        for enlace, (centro, tamaño, color) in self.modelo.cajas.items():
            for cara in caras_de_caja(poses[enlace], centro, tamaño):
                profundidad = sum(proyectar(punto)[2] for punto in cara) / len(cara)
                caras.append((profundidad, cara, color))
        for _, cara, color in sorted(caras, key=lambda cara: cara[0], reverse=True):
            self.lienzo.create_polygon(
                [coord for punto in cara for coord in pantalla(punto)],
                fill=color, outline="#27384c",
            )

        punta = poses["punta"]
        u, v = pantalla((punta.x, punta.y, punta.z))
        self.lienzo.create_oval(u - 3, v - 3, u + 3, v + 3, fill="#501b66", outline="")
        altura = "arriba" if self.z == self.modelo.z_arriba else "abajo"
        self.angulos.set(
            f"Base {self.q[0]:.1f}°    Codo {self.q[1]:.1f}°    "
            f"Punta ({punta.x * 1000:.1f}, {punta.y * 1000:.1f}) mm · {altura}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fisico", nargs=2, type=float, metavar=("BASE", "CODO"),
        help="Activa el PCA9685. Indica los ángulos de la pose física actual.",
    )
    inicial = parser.parse_args().fisico
    if inicial is not None:
        try:
            pulsos_xy(*inicial)
        except ValueError as error:
            parser.error(str(error))

    modelo = ModeloUrdf(Path(__file__).with_name("scara.urdf"))
    ventana = tk.Tk()
    control = None
    if inicial is not None:
        confirmar = messagebox.askokcancel(
            "Activar robot físico",
            f"Coloca el brazo en base {inicial[0]:g}° y codo {inicial[1]:g}°. "
            "Al aceptar, se levantará el marcador. El primer movimiento X/Y "
            "partirá de la postura indicada.",
            parent=ventana,
        )
        if not confirmar:
            ventana.destroy()
            return
        try:
            control = ControlScara()
            control.marcador(True)
        except (ImportError, OSError, ValueError) as error:
            if control is not None:
                try:
                    control.cerrar()
                except OSError:
                    pass
            messagebox.showerror("No se pudo activar el PCA9685", str(error), parent=ventana)
            ventana.destroy()
            return
    Aplicacion(ventana, modelo, control, inicial)
    ventana.mainloop()


if __name__ == "__main__":
    main()
