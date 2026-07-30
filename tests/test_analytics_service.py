from pathlib import Path

from matplotlib.figure import Figure

from gpc_dtwin.services.analytics_service import AnalyticsService
from gpc_dtwin.services.data_service import DataService

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"


def test_all_visual_analytics_figures_build():
    dataframe = DataService.load_csv(DATASET)
    service = AnalyticsService()
    assert len(service.CHARTS) == 10
    for definition in service.CHARTS:
        figure = service.create_figure(dataframe, definition.key, "M2")
        assert isinstance(figure, Figure)
        assert len(figure.axes) >= 1
        figure.clear()
