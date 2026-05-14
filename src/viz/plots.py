"""Project-wide plot styling. Same palette as the midterm Halawi deck."""

NAVY = "#0B2545"
DEEP = "#13315C"
TEAL = "#1C7293"
SKY = "#8DA9C4"
CREAM = "#F6F6F2"
ACCENT = "#EEA02B"
INK = "#1A1A1A"

PALETTE = [NAVY, TEAL, ACCENT, SKY, DEEP]


def apply_style() -> None:
    """Apply matplotlib rcParams for the project palette. Wire up in Phase 2."""
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.prop_cycle": mpl.cycler(color=PALETTE),
            "font.family": "sans-serif",
        }
    )
