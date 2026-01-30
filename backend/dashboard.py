import hvplot.pandas  # noqa: F401
import pandas as pd
import panel as pn

from . import data_manager

pn.extension(template="material")

COLOR_KEY = {"Yes": "green", "No": "red", "Abstain": "orange", "–": "lightgray"}


def votes_heatmap(df: pd.DataFrame) -> pn.pane.HoloViews:
    """Return heatmap visualization for DRep votes."""
    melt = df.reset_index().melt("index", var_name="ga_id", value_name="vote")
    melt = melt.rename(columns={"index": "drep_id"})
    heatmap = melt.hvplot.heatmap(
        x="ga_id", y="drep_id", C="vote", color_key=COLOR_KEY, rot=90
    )
    return pn.pane.HoloViews(heatmap, sizing_mode="stretch_width")


def dashboard() -> pn.Column:
    """Construct the Panel dashboard."""
    active = len(data_manager.get_active_dreps())
    vp_df = data_manager.get_voting_power_per_drep()
    votes_df = data_manager.get_votes_matrix()

    number = pn.indicators.Number(name="Active DReps", value=active)
    bar = vp_df.hvplot.bar(x="drep_id", y="total_voting_power", rot=90)

    return pn.Column(
        pn.pane.Markdown("## Cardano DRep Dashboard"),
        number,
        pn.pane.HoloViews(bar, sizing_mode="stretch_width"),
        votes_heatmap(votes_df),
    )
