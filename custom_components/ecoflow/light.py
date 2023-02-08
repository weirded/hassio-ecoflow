from typing import Any

from homeassistant.components.light import (ColorMode, LightEntity,
                                            LightEntityFeature)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (DOMAIN, EcoFlowData, EcoFlowDevice, EcoFlowEntity,
               EcoFlowExtraDevice, EcoFlowMainDevice)
from .ecoflow import is_river, send

_EFFECTS = ["Low", "High", "SOS"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data: EcoFlowData = hass.data[DOMAIN]

    def device_added(device: EcoFlowDevice):
        entities = []
        if type(device) is EcoFlowMainDevice:
            if is_river(device.product):
                entities.extend([
                    LedEntity(device, device.pd, "light_state", "Light"),
                ])
        elif type(device) is EcoFlowExtraDevice:
            if device.product == 5:  # RIVER Max
                entities.extend([
                    AmbientEntity(device, device.bms,
                                  "ambient", "Ambient light"),
                ])
        async_add_entities(entities)

    entry.async_on_unload(data.device_added.subscribe(device_added).dispose)
    for device in data.devices.values():
        device_added(device)


class AmbientEntity(LightEntity, EcoFlowEntity):
    _attr_effect_list = ["Default", "Breathe", "Flow", "Dynamic", "Rainbow"]
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:led-strip"
    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _last_mode = 1

    async def async_turn_off(self, **kwargs):
        self._device.send(send.set_ambient(0))

    async def async_turn_on(self, brightness=None, rgb_color=None, effect=None, **kwargs):
        if brightness is None:
            brightness = 255
        else:
            brightness = int(brightness * 100 / 255)

        if rgb_color is None:
            rgb_color = (255, 255, 255, 255)
        else:
            rgb_color = list[int](rgb_color)
            rgb_color.append(0)

        if effect is None:
            effect = 255
        else:
            effect = self._attr_effect_list.index(effect)

        self._device.send(send.set_ambient(
            self._last_mode, effect, rgb_color, brightness))

    def _on_updated(self, data: dict[str, Any]):
        self._attr_is_on = data["ambient_mode"] != 0
        self._attr_brightness = int(data["ambient_brightness"] * 255 / 100)
        if self._attr_is_on:
            self._last_mode = data["ambient_mode"]
            self._attr_effect = self._attr_effect_list[data["ambient_animate"]]
            self._attr_color_mode = ColorMode.BRIGHTNESS if data[
                "ambient_animate"] > 1 else ColorMode.RGB
        else:
            self._attr_effect = None
            self._attr_color_mode = None
        self._attr_rgb_color = data["ambient_color"][0:3]


class LedEntity(LightEntity, EcoFlowEntity):
    _attr_effect = _EFFECTS[0]
    _attr_effect_list = _EFFECTS
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT

    def _on_updated(self, data: dict[str, Any]):
        value = data[self._key]
        if value != 0:
            self._attr_is_on = True
            self._attr_effect = _EFFECTS[value - 1]
        else:
            self._attr_is_on = False
            self._attr_effect = None

    async def async_turn_off(self, **kwargs):
        self._device.send(send.set_light(self._device.product, 0))

    async def async_turn_on(self, effect: str = None, **kwargs):
        if not effect:
            effect = self.effect or _EFFECTS[0]
        self._device.send(send.set_light(
            self._device.product, _EFFECTS.index(effect) + 1))
