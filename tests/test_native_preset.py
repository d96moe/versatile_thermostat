# pylint: disable=wildcard-import, unused-wildcard-import, protected-access, unused-argument, line-too-long

"""Tests for native_preset_mode on over_climate VTherm.

When native_preset_mode=True:
- VTherm exposes the underlying climate's own preset list instead of VT temp-based presets.
- Setting a preset sends climate.set_preset_mode to the underlying entity and does NOT
  change VTherm's internal target temperature.
- Temperature can still be set manually and is unaffected by preset changes.
"""

from unittest.mock import patch, call, AsyncMock
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.climate.const import (
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.versatile_thermostat.thermostat_climate import ThermostatOverClimate
from custom_components.versatile_thermostat.const import (
    DOMAIN,
    CONF_THERMOSTAT_TYPE,
    CONF_THERMOSTAT_CLIMATE,
    CONF_NATIVE_PRESET_MODE,
)
from custom_components.versatile_thermostat.vtherm_preset import VThermPreset

from .commons import *  # pylint: disable=wildcard-import, unused-wildcard-import


# Config with native_preset_mode=True
NATIVE_PRESET_CLIMATE_CONFIG = (
    MOCK_TH_OVER_CLIMATE_USER_CONFIG
    | MOCK_TH_OVER_CLIMATE_MAIN_CONFIG
    | MOCK_TH_OVER_CLIMATE_CENTRAL_MAIN_CONFIG
    | {
        CONF_UNDERLYING_LIST: ["climate.mock_climate"],
        CONF_AC_MODE: False,
        CONF_AUTO_REGULATION_MODE: CONF_AUTO_REGULATION_NONE,
        CONF_NATIVE_PRESET_MODE: True,
    }
    | MOCK_ADVANCED_CONFIG
)


async def test_native_preset_mode_exposes_underlying_presets(
    hass: HomeAssistant, skip_hass_states_is_state, skip_send_event
):
    """When native_preset_mode=True, VTherm must expose the underlying climate's
    preset list instead of VT's own temperature-based presets."""

    fake_underlying_climate = await create_and_register_mock_climate(
        hass, "mock_climate", "MockClimateName", {}
    )
    # MockClimate has [PRESET_COMFORT, PRESET_ECO, PRESET_BOOST]
    assert fake_underlying_climate.preset_modes == [PRESET_COMFORT, PRESET_ECO, PRESET_BOOST]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TheOverClimateMockName",
        unique_id="uniqueId_native",
        data=NATIVE_PRESET_CLIMATE_CONFIG,
    )
    tz = get_tz(hass)
    now = datetime.now(tz=tz)

    with patch(
        "custom_components.versatile_thermostat.const.NowClass.get_now",
        return_value=now,
    ):
        entity = await create_thermostat(hass, entry, "climate.theoverclimatemockname")
        assert entity
        assert isinstance(entity, ThermostatOverClimate)
        assert entity.is_over_climate is True
        assert entity.native_preset_mode is True

        await wait_for_local_condition(lambda: entity.is_ready is True)

        # VTherm must expose the underlying climate's presets — NOT VT's temp-based ones
        assert entity.preset_modes is not None
        assert PRESET_COMFORT in entity.preset_modes
        assert PRESET_ECO in entity.preset_modes
        assert PRESET_BOOST in entity.preset_modes
        # VT's own temperature presets must NOT appear
        assert VThermPreset.FROST not in entity.preset_modes


async def test_native_preset_mode_sets_underlying_preset(
    hass: HomeAssistant, skip_hass_states_is_state, skip_send_event
):
    """When native_preset_mode=True, selecting a preset must call set_preset_mode
    on the underlying climate and must NOT change VTherm's target temperature."""

    fake_underlying_climate = await create_and_register_mock_climate(
        hass, "mock_climate", "MockClimateName", {}
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TheOverClimateMockName",
        unique_id="uniqueId_native2",
        data=NATIVE_PRESET_CLIMATE_CONFIG,
    )
    tz = get_tz(hass)
    now = datetime.now(tz=tz)

    with patch(
        "custom_components.versatile_thermostat.const.NowClass.get_now",
        return_value=now,
    ):
        entity = await create_thermostat(hass, entry, "climate.theoverclimatemockname")
        await wait_for_local_condition(lambda: entity.is_ready is True)

        initial_temp = entity.target_temperature

        # Intercept calls to underlying climate
        with patch.object(
            fake_underlying_climate, "async_set_preset_mode", new_callable=AsyncMock
        ) as mock_set_preset:
            await entity.async_set_preset_mode(PRESET_BOOST)
            await hass.async_block_till_done()

            # Underlying climate must receive the preset
            mock_set_preset.assert_called_once_with(PRESET_BOOST)

        # VTherm's target temperature must be unchanged
        assert entity.target_temperature == initial_temp


async def test_native_preset_mode_temperature_unchanged_after_preset(
    hass: HomeAssistant, skip_hass_states_is_state, skip_send_event
):
    """Manual temperature changes must be respected and not overwritten by preset
    changes when native_preset_mode=True."""

    await create_and_register_mock_climate(hass, "mock_climate", "MockClimateName", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TheOverClimateMockName",
        unique_id="uniqueId_native3",
        data=NATIVE_PRESET_CLIMATE_CONFIG,
    )
    tz = get_tz(hass)
    now = datetime.now(tz=tz)

    with patch(
        "custom_components.versatile_thermostat.const.NowClass.get_now",
        return_value=now,
    ):
        entity = await create_thermostat(hass, entry, "climate.theoverclimatemockname")
        await wait_for_local_condition(lambda: entity.is_ready is True)

        # Set manual temperature
        await entity.async_set_temperature(temperature=22.0)
        await hass.async_block_till_done()
        assert entity.target_temperature == 22.0

        # Set a preset — must NOT overwrite the manual temperature
        await entity.async_set_preset_mode(PRESET_ECO)
        await hass.async_block_till_done()
        assert entity.target_temperature == 22.0


async def test_normal_preset_mode_unaffected(
    hass: HomeAssistant, skip_hass_states_is_state, skip_send_event, fake_underlying_climate
):
    """Without native_preset_mode, VTherm must behave exactly as before —
    exposing its own temperature-based presets (regression guard)."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TheOverClimateMockName",
        unique_id="uniqueId",
        data=PARTIAL_CLIMATE_NOT_REGULATED_CONFIG,
    )
    tz = get_tz(hass)
    now = datetime.now(tz=tz)

    with patch(
        "custom_components.versatile_thermostat.const.NowClass.get_now",
        return_value=now,
    ):
        entity = await create_thermostat(hass, entry, "climate.theoverclimatemockname")
        await wait_for_local_condition(lambda: entity.is_ready is True)

        assert entity.native_preset_mode is False
        # VT's own temperature-based presets must still be there
        assert VThermPreset.ECO in entity.preset_modes
        assert VThermPreset.COMFORT in entity.preset_modes
