"""Explicit secure lookup metadata for FK display fields."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from ....domain.modelo.dtos import ReferenceFieldDTO


@dataclass(frozen=True)
class ReferenceFieldProfile:
    catalog_name: str
    field_name: str
    label: str
    owner_resource: str
    lookup_key: str
    display_field_key: str
    search_function_name: str
    resolve_function_name: str
    min_search_chars: int = 2
    page_size: int = 20
    value_field: str = "id"
    label_field: str = "label"
    search_context_keys: tuple[str, ...] = ()

    def to_reference_dto(self) -> ReferenceFieldDTO:
        return ReferenceFieldDTO(
            lookup_key=self.lookup_key,
            min_search_chars=self.min_search_chars,
            page_size=self.page_size,
            value_field=self.value_field,
            label_field=self.label_field,
        )


class ReferenceProfileRegistry:
    """Lookup metadata indexed by catalog/field and lookup key."""

    def __init__(self, profiles: tuple[ReferenceFieldProfile, ...] = ()) -> None:
        normalized = tuple(
            ReferenceFieldProfile(
                catalog_name=profile.catalog_name.strip().lower(),
                field_name=profile.field_name.strip(),
                label=profile.label.strip(),
                owner_resource=profile.owner_resource.strip().lower(),
                lookup_key=profile.lookup_key.strip().lower(),
                display_field_key=profile.display_field_key.strip(),
                search_function_name=profile.search_function_name.strip(),
                resolve_function_name=profile.resolve_function_name.strip(),
                min_search_chars=int(profile.min_search_chars),
                page_size=int(profile.page_size),
                value_field=profile.value_field.strip(),
                label_field=profile.label_field.strip(),
                search_context_keys=tuple(
                    str(key).strip()
                    for key in profile.search_context_keys
                    if str(key).strip()
                ),
            )
            for profile in profiles
        )
        self._profiles = normalized
        self._by_catalog_field = {
            (profile.catalog_name, profile.field_name): profile
            for profile in normalized
        }
        self._by_lookup_key = {profile.lookup_key: profile for profile in normalized}
        grouped: dict[str, list[ReferenceFieldProfile]] = defaultdict(list)
        for profile in normalized:
            grouped[profile.catalog_name].append(profile)
        self._by_catalog = {catalog_name: tuple(items) for catalog_name, items in grouped.items()}

    def field_profile(self, catalog_name: str, field_name: str) -> ReferenceFieldProfile | None:
        return self._by_catalog_field.get((str(catalog_name).lower(), str(field_name)))

    def profiles_for_catalog(self, catalog_name: str) -> tuple[ReferenceFieldProfile, ...]:
        return self._by_catalog.get(str(catalog_name).lower(), ())

    def lookup_profile(self, lookup_key: str) -> ReferenceFieldProfile:
        normalized = str(lookup_key).strip().lower()
        if normalized not in self._by_lookup_key:
            raise KeyError(f"Lookup no registrado: {lookup_key}")
        return self._by_lookup_key[normalized]


DEFAULT_REFERENCE_PROFILES = ReferenceProfileRegistry(
    (
        ReferenceFieldProfile(
            catalog_name="conductor",
            field_name="camion_id",
            label="Camion",
            owner_resource="conductor",
            lookup_key="conductor.camion_id",
            display_field_key="camion_label",
            search_function_name="ui_ref.conductor_camion_search",
            resolve_function_name="ui_ref.conductor_camion_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="conductor",
            field_name="furgon_id",
            label="Furgon",
            owner_resource="conductor",
            lookup_key="conductor.furgon_id",
            display_field_key="furgon_label",
            search_function_name="ui_ref.conductor_furgon_search",
            resolve_function_name="ui_ref.conductor_furgon_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="conductor",
            field_name="thermo_id",
            label="Thermo",
            owner_resource="conductor",
            lookup_key="conductor.thermo_id",
            display_field_key="thermo_label",
            search_function_name="ui_ref.conductor_thermo_search",
            resolve_function_name="ui_ref.conductor_thermo_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="ruta",
            field_name="origen_id",
            label="Origen",
            owner_resource="ruta",
            lookup_key="ruta.origen_id",
            display_field_key="origen_label",
            search_function_name="ui_ref.ruta_origen_search",
            resolve_function_name="ui_ref.ruta_origen_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="ruta",
            field_name="destino_id",
            label="Destino",
            owner_resource="ruta",
            lookup_key="ruta.destino_id",
            display_field_key="destino_label",
            search_function_name="ui_ref.ruta_destino_search",
            resolve_function_name="ui_ref.ruta_destino_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="tarifa_flete",
            field_name="cliente_id",
            label="Cliente",
            owner_resource="tarifa_flete",
            lookup_key="tarifa_flete.cliente_id",
            display_field_key="cliente_label",
            search_function_name="ui_ref.tarifa_flete_cliente_search",
            resolve_function_name="ui_ref.tarifa_flete_cliente_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="tarifa_flete",
            field_name="ruta_id",
            label="Ruta",
            owner_resource="tarifa_flete",
            lookup_key="tarifa_flete.ruta_id",
            display_field_key="ruta_label",
            search_function_name="ui_ref.tarifa_flete_ruta_search",
            resolve_function_name="ui_ref.tarifa_flete_ruta_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="cliente_id",
            label="Cliente",
            owner_resource="viaje",
            lookup_key="viaje.cliente_id",
            display_field_key="cliente_label",
            search_function_name="ui_ref.viaje_cliente_search",
            resolve_function_name="ui_ref.viaje_cliente_resolve",
            search_context_keys=("trip_type",),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="origen_id",
            label="Origen",
            owner_resource="viaje",
            lookup_key="viaje.origen_id",
            display_field_key="origen_label",
            search_function_name="ui_ref.viaje_origen_search",
            resolve_function_name="ui_ref.viaje_origen_resolve",
            search_context_keys=("cliente_id", "destino_id"),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="destino_id",
            label="Destino",
            owner_resource="viaje",
            lookup_key="viaje.destino_id",
            display_field_key="destino_label",
            search_function_name="ui_ref.viaje_destino_search",
            resolve_function_name="ui_ref.viaje_destino_resolve",
            search_context_keys=("cliente_id", "origen_id"),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="conductor_id",
            label="Conductor",
            owner_resource="viaje",
            lookup_key="viaje.conductor_id",
            display_field_key="conductor_label",
            search_function_name="ui_ref.viaje_conductor_search",
            resolve_function_name="ui_ref.viaje_conductor_resolve",
            search_context_keys=("trip_type", "include_agregados"),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="furgon_id",
            label="Furgon",
            owner_resource="viaje",
            lookup_key="viaje.furgon_id",
            display_field_key="furgon_label",
            search_function_name="ui_ref.viaje_furgon_search",
            resolve_function_name="ui_ref.viaje_furgon_resolve",
            search_context_keys=("include_agregados",),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="camion_id",
            label="Camion",
            owner_resource="viaje",
            lookup_key="viaje.camion_id",
            display_field_key="camion_label",
            search_function_name="ui_ref.viaje_camion_search",
            resolve_function_name="ui_ref.viaje_camion_resolve",
            search_context_keys=("include_agregados",),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="thermo_id",
            label="Thermo",
            owner_resource="viaje",
            lookup_key="viaje.thermo_id",
            display_field_key="thermo_label",
            search_function_name="ui_ref.viaje_thermo_search",
            resolve_function_name="ui_ref.viaje_thermo_resolve",
            search_context_keys=("include_agregados",),
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="_ruta_id",
            label="Ruta",
            owner_resource="viaje",
            lookup_key="viaje._ruta_id",
            display_field_key="ruta_label",
            search_function_name="ui_ref.viaje_ruta_search",
            resolve_function_name="ui_ref.viaje_ruta_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="_circuito_id",
            label="Circuito",
            owner_resource="viaje",
            lookup_key="viaje._circuito_id",
            display_field_key="circuito_label",
            search_function_name="ui_ref.viaje_circuito_search",
            resolve_function_name="ui_ref.viaje_circuito_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="viaje",
            field_name="viaje_ida_id",
            label="Viaje de ida",
            owner_resource="viaje",
            lookup_key="viaje.viaje_ida_id",
            display_field_key="viaje_ida_label",
            search_function_name="ui_ref.viaje_ida_search",
            resolve_function_name="ui_ref.viaje_ida_resolve",
            search_context_keys=("conductor_id", "camion_id"),
        ),
        ReferenceFieldProfile(
            catalog_name="factura",
            field_name="cliente_id",
            label="Cliente",
            owner_resource="factura",
            lookup_key="factura.cliente_id",
            display_field_key="cliente_label",
            search_function_name="ui_ref.factura_cliente_search",
            resolve_function_name="ui_ref.factura_cliente_resolve",
        ),
        ReferenceFieldProfile(
            catalog_name="recibo",
            field_name="cliente_id",
            label="Cliente",
            owner_resource="recibo",
            lookup_key="recibo.cliente_id",
            display_field_key="cliente_label",
            search_function_name="ui_ref.recibo_cliente_search",
            resolve_function_name="ui_ref.recibo_cliente_resolve",
        ),
    )
)
