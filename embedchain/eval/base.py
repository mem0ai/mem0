from abc import ABC

from .utils import EvalData


class BaseMetric(ABC):
    """Base class for a metric.

    This class provides a common interface for all metrics.
    """

    def __init__(self):
        """
        Initialize the BaseMetric.
        """

    def evaluate_data(self, dataset: list[EvalData]):
        """Evaluate the dataset.

        param: dataset: The dataset to evaluate.
        """
        raise NotImplementedError
