from miio.miot_device import MiotDevice as MiotDeviceOriginal

class MiotDevice(MiotDeviceOriginal):
    def __init__(
        self,
        mapping: dict = {},
        ip: str = None,
        token: str = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
    ) -> None:
        try:
            super().__init__(ip=ip, token=str(token), start_id=start_id,
                            debug=debug, lazy_discover=lazy_discover, mapping=mapping)
        except TypeError:
            super().__init__(ip=ip, token=str(token), start_id=start_id,
                            debug=debug, lazy_discover=lazy_discover)
            self.mapping = mapping

    def get_properties_for_mapping(self, max_properties=10) -> list:
        """Retrieve raw properties based on mapping."""

        # We send property key in "did" because it's sent back via response and we can identify the property.
        properties = [
            {"did": k, **v} for k, v in self.mapping.items() if "aiid" not in v
        ]

        return self.get_properties(
            properties, property_getter="get_properties", max_properties=max_properties
        )
