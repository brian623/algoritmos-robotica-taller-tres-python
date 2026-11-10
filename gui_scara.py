"""Posicionamiento y simulación visual del SCARA del Taller 3."""

import tkinter as tk
from dataclasses import dataclass
from math import cos, radians, sin
from pathlib import Path
from time import monotonic
from tkinter import ttk
from xml.etree import ElementTree

from cinematica import Scara


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
    def __init__(self, ventana, modelo):
        self.ventana = ventana
        self.modelo = modelo
        self.q = modelo.cinematica.inversa(160, 100)
        self.z = modelo.z_arriba
        self.objetivo = (160, 100)
        self.animacion = None
        self.contorno = [(x / 1000, y / 1000, 0) for x, y in modelo.cinematica.contorno()]

        ventana.title("Taller 3 · Robot SCARA")
        ventana.minsize(640, 480)
        ventana.columnconfigure(0, weight=1)
        ventana.rowconfigure(1, weight=1)
        controles = ttk.Frame(ventana, padding=12)
        controles.grid(row=0, column=0, sticky="ew")
        self.x = tk.StringVar(value="160")
        self.y = tk.StringVar(value="100")
        for columna, (etiqueta, variable) in enumerate((("X (mm)", self.x), ("Y (mm)", self.y))):
            ttk.Label(controles, text=etiqueta).grid(row=0, column=2 * columna, padx=(0, 5))
            entrada = ttk.Entry(controles, textvariable=variable, width=9)
            entrada.grid(row=0, column=2 * columna + 1, padx=(0, 12))
            entrada.bind("<Return>", lambda _: self.mover())
        ttk.Button(controles, text="Mover a X/Y", command=self.mover).grid(row=0, column=4)
        ttk.Button(controles, text="Subir / bajar punta", command=self.cambiar_altura).grid(
            row=0, column=5, padx=(8, 0)
        )
        self.angulos = tk.StringVar()
        ttk.Label(controles, textvariable=self.angulos).grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(9, 0)
        )
        self.lienzo = tk.Canvas(ventana, bg="#f5f8fa", highlightthickness=0, width=760, height=470)
        self.lienzo.grid(row=1, column=0, sticky="nsew", padx=12)
        self.lienzo.bind("<Configure>", lambda _: self.dibujar())
        self.estado = tk.StringVar(value="Simulación URDF. Ingresa un punto dentro del contorno.")
        ttk.Label(ventana, textvariable=self.estado, padding=12).grid(row=2, column=0, sticky="ew")

    def mover(self):
        try:
            x, y = (float(campo.get().replace(",", ".")) for campo in (self.x, self.y))
        except ValueError:
            self.estado.set("Ingresa números válidos para X e Y.")
            return
        try:
            destino = self.modelo.cinematica.inversa(x, y)
        except ValueError as error:
            self.estado.set(str(error))
            return

        if self.animacion is not None:
            self.ventana.after_cancel(self.animacion)
        self.objetivo = (x, y)
        self.z = self.modelo.z_arriba
        self.estado.set(f"Moviendo a ({x:g}, {y:g}) mm.")
        origen = self.q
        inicio = monotonic()
        duracion = max(abs(a - b) for a, b in zip(origen, destino)) / 120

        def avanzar():
            fraccion = min(1.0, (monotonic() - inicio) / duracion) if duracion else 1.0
            self.q = tuple(a + fraccion * (b - a) for a, b in zip(origen, destino))
            self.dibujar()
            if fraccion < 1:
                self.animacion = self.ventana.after(25, avanzar)
            else:
                self.animacion = None
                self.estado.set(f"Punto alcanzado en simulación: ({x:g}, {y:g}) mm.")

        avanzar()

    def cambiar_altura(self):
        if self.animacion is not None:
            self.estado.set("Espera a que termine el movimiento X/Y.")
            return
        self.z = self.modelo.z_abajo if self.z == self.modelo.z_arriba else self.modelo.z_arriba
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
    modelo = ModeloUrdf(Path(__file__).with_name("scara.urdf"))
    ventana = tk.Tk()
    Aplicacion(ventana, modelo)
    ventana.mainloop()


if __name__ == "__main__":
    main()
