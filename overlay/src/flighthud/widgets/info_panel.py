"""Simple top-right telemetry readout (GS / ALT / V/S / TRACK / WIND).

Replica del overlay "simple" de joseflys (/replay): un panel redondeado
semitransparente con filas de etiqueta (chica, atenuada, en mayúsculas) sobre
un valor grande en blanco. Mismos colores, borde y transparencia que el HUD
web de joseflys (slate-900 @ 0.8, borde slate-600, etiquetas slate-400).

Es totalmente configurable desde el template: cada fila declara su etiqueta,
la columna del CSV y el formato. Si no se pasan ``rows`` usa el set por defecto.
"""

from matplotlib.patches import FancyBboxPatch

from .base import Widget, register

# Paleta de joseflys (Tailwind slate), en RGBA 0–1.
_BG = (15 / 255, 23 / 255, 42 / 255, 0.80)      # slate-900 @ 80%
_BORDER = (71 / 255, 85 / 255, 105 / 255, 1.0)  # slate-600
_LABEL = (148 / 255, 163 / 255, 184 / 255, 1.0)  # slate-400
_VALUE = "white"

# Puntos → píxeles de datos: la figura es dpi=100 y 1 unidad de dato = 1 px,
# mientras que fontsize está en puntos (1 pt = 1/72").
_PT_TO_PX = 100 / 72

# Filas por defecto: equivalente al panel "simple" de joseflys + viento, que la
# aviónica Garmin ya calcula y registra en el log (no se deriva acá).
DEFAULT_ROWS = [
    {"label": "GS", "source": "GPS Ground Speed (kt)", "unit": " KT"},
    {"label": "ALT", "source": "Baro Altitude (ft)", "unit": " ft", "thousands": True},
    {"label": "V/S", "source": "Vertical Speed (ft/min)", "unit": " fpm", "signed": True},
    {"label": "TRACK", "source": "GPS Ground Track (deg)", "unit": "°",
     "angular": True, "pad3": True},
    {"label": "WIND", "kind": "wind",
     "dir_source": "Wind Direction (deg)", "speed_source": "Wind Speed (kt)"},
]


@register
class InfoPanel(Widget):
    """Panel redondeado con filas etiqueta-sobre-valor, anclado por su borde superior.

    Config (todas opcionales salvo posición):
      x, y          : esquina superior-izquierda del panel (y crece hacia arriba;
                      el panel se dibuja hacia abajo desde ``y``).
      width         : ancho del panel (px). Default 230.
      rows          : lista de filas (ver abajo). Default ``DEFAULT_ROWS``.
      pad           : margen interno (px). Default 18.
      label_size    : tamaño de la etiqueta (pt). Default 10.
      value_size    : tamaño del valor (pt). Default 20.
      label_gap     : separación etiqueta→valor (px). Default 4.
      row_gap       : separación valor→siguiente etiqueta (px). Default 16.
      radius        : radio de las esquinas (px). Default 14.
      border_width  : grosor del borde. Default 1.0 (0 = sin borde).
      bg_color / border_color / label_color / value_color : overrides de paleta.
      zorder        : Default 1.

    Cada fila es un dict:
      label         : texto de la etiqueta (se muestra en mayúsculas).
      kind          : "value" (default) | "wind".
      source        : columna del CSV (para kind="value").
      unit          : sufijo, p.ej. " KT", " ft", "°".
      decimals      : decimales. Default 0.
      transform     : "identity" | "fahrenheit_to_celsius" | "gph_to_lph".
      angular       : interpolar como ángulo (wrap 0–360). Default False.
      pad3          : rellenar a 3 dígitos (rumbos). Default False.
      thousands     : separador de miles. Default False.
      signed        : prefijo "+" en positivos (V/S). Default False.
      dir_source / speed_source : columnas para kind="wind".
    """

    type = "info_panel"

    def _layout(self):
        """Calcula geometría y posiciones de filas (px, una sola vez)."""
        self._rows = self.get("rows") or DEFAULT_ROWS
        self._x = self.get("x", 0)
        self._top = self.get("y", 0)
        self._w = self.get("width", 230)
        self._pad = self.get("pad", 18)
        self._label_size = self.get("label_size", 10)
        self._value_size = self.get("value_size", 20)
        label_gap = self.get("label_gap", 4)
        row_gap = self.get("row_gap", 16)

        label_h = self._label_size * _PT_TO_PX
        value_h = self._value_size * _PT_TO_PX
        row_height = label_h + label_gap + value_h + row_gap

        n = len(self._rows)
        inner_h = n * row_height - row_gap if n else 0
        self._h = inner_h + 2 * self._pad
        self._bottom = self._top - self._h

        inner_top = self._top - self._pad
        text_x = self._x + self._pad
        # Por fila: (x, y_etiqueta, y_valor)
        self._positions = []
        for i in range(n):
            label_y = inner_top - i * row_height
            value_y = label_y - label_h - label_gap
            self._positions.append((text_x, label_y, value_y))

    def draw_static(self, ax):
        self._layout()
        z = self.get("zorder", 1)

        radius = self.get("radius", 14)
        ax.add_patch(
            FancyBboxPatch(
                (self._x, self._bottom), self._w, self._h,
                boxstyle=f"round,pad=0,rounding_size={radius}",
                mutation_aspect=1,
                facecolor=tuple(self.get("bg_color", _BG)),
                edgecolor=tuple(self.get("border_color", _BORDER)),
                linewidth=self.get("border_width", 1.0),
                zorder=z,
            )
        )

        label_color = self.get("label_color", _LABEL)
        if isinstance(label_color, list):
            label_color = tuple(label_color)
        for (tx, label_y, _), row in zip(self._positions, self._rows):
            ax.text(
                tx, label_y, str(row.get("label", "")).upper(),
                fontsize=self._label_size, color=label_color, weight="bold",
                ha="left", va="top", zorder=z + 1,
            )

    def create_dynamic(self, ax):
        z = self.get("zorder", 1)
        value_color = self.get("value_color", _VALUE)
        if isinstance(value_color, list):
            value_color = tuple(value_color)
        self._values = []
        for (tx, _, value_y), row in zip(self._positions, self._rows):
            artist = ax.text(
                tx, value_y, "",
                fontsize=self._value_size, color=value_color, weight="bold",
                ha="left", va="top", zorder=z + 2,
            )
            self._values.append((artist, row))

    def update(self, fd):
        for artist, row in self._values:
            artist.set_text(_format_row(fd, row))


def _format_row(fd, row):
    """Formatea el valor de una fila según su tipo/flags. '--' si falta el dato."""
    if row.get("kind") == "wind":
        d = fd.value(row.get("dir_source", "Wind Direction (deg)"), angular=True)
        s = fd.value(row.get("speed_source", "Wind Speed (kt)"))
        if d is None or s is None:
            return "--"
        return f"{int(round(d)):03d}° / {int(round(s))} KT"

    v = fd.value(
        row.get("source"),
        transform=row.get("transform", "identity"),
        angular=row.get("angular", False),
    )
    if v is None:
        return "--"

    dec = row.get("decimals", 0)
    if row.get("pad3"):
        text = f"{int(round(v)):03d}"
    elif row.get("thousands"):
        text = f"{v:,.{dec}f}" if dec else f"{int(round(v)):,d}"
    else:
        text = f"{v:.{dec}f}"
    if row.get("signed") and v > 0:
        text = "+" + text
    return text + row.get("unit", "")
