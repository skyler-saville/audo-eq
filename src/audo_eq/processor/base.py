from abc import ABC, abstractmethod
import numpy as np


class BaseProcessor(ABC):
    """Base class for all processing modules."""

    @abstractmethod
    def process(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        """Process audio and return the transformed signal."""
        raise NotImplementedError
