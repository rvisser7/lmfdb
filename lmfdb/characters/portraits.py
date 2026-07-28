# -*- coding: utf-8 -*-
r"""
Portraits (Gauss-sum visualizations) for Dirichlet characters.

Following the design proposed in https://github.com/LMFDB/lmfdb/issues/3996
(see the demo at https://alexjbest.github.io/dirich/), the portrait of a
Dirichlet character `\chi` of modulus `N` shows, for each residue
`a \in \{0, \dots, N-1\}`, the partial Gauss sums

.. MATH::

    S_a(k) = \sum_{n=1}^{k} \chi(n) e^{2\pi i a n / N},
    \qquad k = 1, \dots, N-1,

as radial segments from the origin, colored by `a` (rainbow hue), with early
partial sums darkened and later ones at full brightness.  A large dot of the
same color marks the complete Gauss sum `\tau_a(\chi) = S_a(N-1)`, and a grey
circle of radius `\sqrt{N}` is drawn: for a primitive character every dot with
`\gcd(a, N) = 1` lands exactly on this circle, so primitivity (and much else:
the order of the character as rotational symmetry, reality as symmetry about
the real axis, triviality as a red horizontal spike) is visible at a glance.

The plot is computed on the fly, so we only do it for small modulus
(`N \le PORTRAIT_MAX_MODULUS`); the number of segments drawn is
`N \cdot \phi(N)`, and rendering time grows accordingly.  For speed the
segments are rendered as a single matplotlib ``LineCollection`` wrapped in a
sage ``GraphicPrimitive``, so the result is an ordinary sage ``Graphics``
object that is embedded in the page via ``encode_plot``, as for elliptic
curve and Maass form plots.
"""

from sage.all import Graphics, circle, gcd, sqrt
from sage.plot.colors import rainbow
from sage.plot.plot import minmax_data
from sage.plot.primitive import GraphicPrimitive

from lmfdb.characters.TinyConrey import ConreyCharacter
from lmfdb.logger import logger
from lmfdb.utils import encode_plot

# Portraits are only computed on the fly for modulus at most this bound
# (roughly 0.1s of rendering time at N = 300, growing to several seconds by
# N = 1000, hence the cutoff).  If portraits are ever precomputed and stored
# in the database, this restriction can be lifted.
PORTRAIT_MAX_MODULUS = 300


class PartialGaussSums(GraphicPrimitive):
    """
    Graphics primitive drawing all partial Gauss sums of a Dirichlet
    character as radial segments, and the complete Gauss sums as dots.

    Rendering ``N * phi(N)`` segments as individual sage lines is far too
    slow, so this primitive holds them in numpy arrays and renders them as a
    single matplotlib ``LineCollection`` (plus one scatter plot for the dots).
    """
    def __init__(self, segments, segment_colors, dots, dot_colors):
        self.segments = segments  # (k, 2, 2): k segments from (0,0) to S_a(n)
        self.segment_colors = segment_colors  # (k, 4) rgba
        self.dots = dots  # (N, 2): complete Gauss sums
        self.dot_colors = dot_colors  # (N, 4) rgba
        GraphicPrimitive.__init__(self, {})

    def get_minmax_data(self):
        xdata = list(self.segments[:, :, 0].flatten()) + list(self.dots[:, 0])
        ydata = list(self.segments[:, :, 1].flatten()) + list(self.dots[:, 1])
        return minmax_data(xdata, ydata, dict=True)

    def _render_on_subplot(self, subplot):
        from matplotlib.collections import LineCollection
        subplot.add_collection(
            LineCollection(self.segments, colors=self.segment_colors,
                           linewidths=1.5, zorder=2))
        subplot.scatter(self.dots[:, 0], self.dots[:, 1], s=60,
                        c=self.dot_colors, zorder=10)


def partial_gauss_sums(modulus, number):
    """
    The partial Gauss sums of the Dirichlet character
    `\\chi_{modulus}(number, \\cdot)`.

    Returns a pair ``(ns, sums)`` of numpy arrays, where ``ns`` lists the
    `n \\in \\{1, \\dots, N-1\\}` coprime to `N = modulus` and ``sums`` has
    shape ``(N, len(ns))`` with ``sums[a, k]`` the partial Gauss sum
    `S_a(ns[k])`; in particular ``sums[a, -1]`` is the complete Gauss sum
    `\\tau_a(\\chi)`.
    """
    import numpy as np

    N = modulus
    chi = ConreyCharacter(N, number)
    # the n with chi(n) != 0, and chi(n) = e(angle(n)) for those n
    ns = np.array([n for n in range(1, N) if gcd(n, N) == 1])
    angles = np.array([float(chi.conreyangle(int(n))) for n in ns])
    chivals = np.exp(2j * np.pi * angles)
    # partial sums S_a(n) for all a (rows) and n in ns (columns)
    avals = np.arange(N)
    phases = np.exp(2j * np.pi * np.outer(avals, ns) / N)
    return ns, np.cumsum(chivals[np.newaxis, :] * phases, axis=1)


def paint_portrait(modulus, number):
    """
    The portrait of the Dirichlet character `\\chi_{modulus}(number, \\cdot)`
    as a base64-encoded png data URI, or ``None`` if the modulus exceeds
    ``PORTRAIT_MAX_MODULUS``.
    """
    if modulus > PORTRAIT_MAX_MODULUS:
        return None
    import numpy as np

    N = modulus
    if N == 1:
        # chi(n) = 1 for all n; tau_0 = 1 is the only (empty) Gauss sum
        segments = np.zeros((0, 2, 2))
        segment_colors = np.zeros((0, 4))
        dots = np.array([[1.0, 0.0]])
        dot_colors = np.array([[1.0, 0.0, 0.0, 0.8]])
    else:
        ns, sums = partial_gauss_sums(N, number)

        # rainbow color for each a, darkened for early partial sums as in
        # the demo: darker(3*(N-1-n)/(5*N)) scales rgb by 1 - 3*(N-1-n)/(5*N)
        base = np.array([[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)]
                         for h in rainbow(N)]) / 255.0
        brightness = 1.0 - 3.0 * (N - 1 - ns) / (5.0 * N)

        k = N * len(ns)
        segments = np.zeros((k, 2, 2))
        segments[:, 1, 0] = sums.real.flatten()
        segments[:, 1, 1] = sums.imag.flatten()
        segment_colors = np.empty((k, 4))
        segment_colors[:, :3] = (base[:, np.newaxis, :]
                                 * brightness[np.newaxis, :, np.newaxis]
                                 ).reshape(k, 3)
        segment_colors[:, 3] = 0.35

        dots = np.column_stack([sums[:, -1].real, sums[:, -1].imag])
        dot_colors = np.empty((N, 4))
        dot_colors[:, :3] = base
        dot_colors[:, 3] = 0.8

    G = Graphics()
    G.add_primitive(PartialGaussSums(segments, segment_colors,
                                     dots, dot_colors))
    G += circle((0, 0), sqrt(modulus), color="grey", zorder=1)
    G.set_aspect_ratio(1)
    G.axes(False)
    return encode_plot(G, pad=0, pad_inches=0, transparent=True,
                       remove_axes=True, axes_pad=0.05, figsize=[4, 4])


def portrait_properties(modulus, number):
    """
    The portrait of `\\chi_{modulus}(number, \\cdot)` as a ``(None, html)``
    pair ready to drop into a properties box: a thumbnail linking to the
    full-size image, exactly as elliptic curve and Maass form plots do.
    Returns ``None`` when the portrait is skipped (modulus above
    ``PORTRAIT_MAX_MODULUS``), so callers can test the result directly.
    """
    uri = paint_portrait(modulus, number)
    if uri is None:
        return None
    link = '<a href="{0}"><img src="{0}" width="200" height="200"/></a>'.format(uri)
    return (None, link)


def add_portrait(info, modulus, number):
    """
    Insert the portrait of `\\chi_{modulus}(number, \\cdot)` into the
    properties box carried by ``info['properties']``, just below the label
    (the position used for the elliptic curve plot).  A no-op when the
    portrait is skipped for large modulus or when ``info`` has no properties
    box, so it is safe to call unconditionally from the character route.

    Any failure while building the portrait is logged and swallowed: the
    portrait is decorative and must never break the character page.
    """
    try:
        entry = portrait_properties(modulus, number)
    except Exception:
        logger.error("failed to build portrait for character %s.%s",
                     modulus, number, exc_info=True)
        return
    if entry is not None and info.get("properties"):
        info["properties"].insert(1, entry)
