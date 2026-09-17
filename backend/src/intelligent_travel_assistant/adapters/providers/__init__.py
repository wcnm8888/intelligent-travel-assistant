"""Concrete external provider adapters."""

from intelligent_travel_assistant.adapters.providers.amap import (
    AMAP_BASE_URL,
    AMAP_POI_NAMESPACE,
    AmapAdapter,
    AmapAdapterConfig,
)
from intelligent_travel_assistant.adapters.providers.deepseek import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
)
from intelligent_travel_assistant.adapters.providers.f009_amap import F009AmapProvider
from intelligent_travel_assistant.adapters.providers.f009_deepseek import (
    F009DeepSeekNarrativeProvider,
)
from intelligent_travel_assistant.adapters.providers.f014_deepseek import (
    F014DeepSeekAdvisorProvider,
)
from intelligent_travel_assistant.adapters.providers.qweather import (
    QWEATHER_TIMEOUT_SECONDS,
    QWeatherAdapter,
    QWeatherAdapterConfig,
)

__all__ = [
    "AMAP_BASE_URL",
    "AMAP_POI_NAMESPACE",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "QWEATHER_TIMEOUT_SECONDS",
    "AmapAdapter",
    "AmapAdapterConfig",
    "DeepSeekAdapter",
    "DeepSeekAdapterConfig",
    "F009AmapProvider",
    "F009DeepSeekNarrativeProvider",
    "F014DeepSeekAdvisorProvider",
    "QWeatherAdapter",
    "QWeatherAdapterConfig",
]
