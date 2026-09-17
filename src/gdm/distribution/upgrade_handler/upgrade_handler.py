from collections import Counter

from pydantic import (
    GetCoreSchemaHandler,
    model_validator,
    SkipValidation,
    ConfigDict,
    BaseModel,
)
from pydantic_core import core_schema

from semver import Version

from gdm.distribution.upgrade_handler.from__2_0_1__to__2_1_2 import from__2_0_1__to__2_1_2
from gdm.distribution.upgrade_handler.from__2_1_2__to__2_1_3 import from__2_1_2__to__2_1_3
from gdm.distribution.upgrade_handler.from__2_1_3__to__2_1_4 import from__2_1_3__to__2_1_4
from gdm.distribution.upgrade_handler.from__2_1_4__to__2_1_5 import from__2_1_4__to__2_1_5
from gdm.distribution.upgrade_handler.from__2_1_5__to__2_2_0 import from__2_1_5__to__2_2_0
from gdm.distribution.upgrade_handler.from__2_2_0__to__2_2_1 import from__2_2_0__to__2_2_1
from gdm.distribution.upgrade_handler.from__2_2_1__to__2_3_0 import from__2_2_1__to__2_3_0
from gdm.distribution.upgrade_handler.from__2_3_0__to__2_3_1 import from__2_3_0__to__2_3_1
from gdm.distribution.upgrade_handler.from__2_3_1__to__2_3_2 import from__2_3_1__to__2_3_2
from gdm.distribution.upgrade_handler.from__2_3_2__to__2_3_3 import from__2_3_2__to__2_3_3
from gdm.distribution.upgrade_handler.from__2_3_3__to__2_3_4 import from__2_3_3__to__2_3_4
from gdm.distribution.upgrade_handler.from__2_3_4__to__2_3_5 import from__2_3_4__to__2_3_5
from gdm.distribution.upgrade_handler.from__2_3_5__to__2_3_6 import from__2_3_5__to__2_3_6
from gdm.distribution.upgrade_handler.from__2_3_6__to__2_3_7 import from__2_3_6__to__2_3_7
from gdm.distribution.upgrade_handler.from__2_3_7__to__2_3_8 import from__2_3_7__to__2_3_8


def fix_version(version):
    if version.count(".") >= 3:
        return version.rsplit(".", 1)[0]
    return version


class SemanticVersion(Version):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler):
        return core_schema.with_info_after_validator_function(
            cls.parse,  # your parsing function
            core_schema.str_schema(),  # input type is a string
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class UpgradeSchema(BaseModel):
    method: SkipValidation
    from_version: SemanticVersion
    to_version: SemanticVersion

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def validate_version(self):
        if self.from_version > self.to_version:
            raise ValueError(
                f"from_version {str(self.from_version)} should be lower than the to_version {str(self.to_version)}"
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def preprocess_input(cls, data):
        data["from_version"] = fix_version(data["from_version"])
        data["to_version"] = fix_version(data["to_version"])

        return data


class UpgradeHandler(BaseModel):
    upgrade_schemas: list[UpgradeSchema] = [
        UpgradeSchema(
            method=from__2_0_1__to__2_1_2,
            from_version="2.0.1",
            to_version="2.1.2",
        ),
        UpgradeSchema(
            method=from__2_1_2__to__2_1_3,
            from_version="2.1.2",
            to_version="2.1.3",
        ),
        UpgradeSchema(
            method=from__2_1_3__to__2_1_4,
            from_version="2.1.3",
            to_version="2.1.4",
        ),
        UpgradeSchema(
            method=from__2_1_4__to__2_1_5,
            from_version="2.1.4",
            to_version="2.1.5",
        ),
        UpgradeSchema(
            method=from__2_1_5__to__2_2_0,
            from_version="2.1.5",
            to_version="2.2.0",
        ),
        UpgradeSchema(
            method=from__2_2_0__to__2_2_1,
            from_version="2.2.0",
            to_version="2.2.1",
        ),
        UpgradeSchema(
            method=from__2_2_1__to__2_3_0,
            from_version="2.2.1",
            to_version="2.3.0",
        ),
        UpgradeSchema(
            method=from__2_3_0__to__2_3_1,
            from_version="2.3.0",
            to_version="2.3.1",
        ),
        UpgradeSchema(
            method=from__2_3_1__to__2_3_2,
            from_version="2.3.1",
            to_version="2.3.2",
        ),
        UpgradeSchema(
            method=from__2_3_2__to__2_3_3,
            from_version="2.3.2",
            to_version="2.3.3",
        ),
        UpgradeSchema(
            method=from__2_3_3__to__2_3_4,
            from_version="2.3.3",
            to_version="2.3.4",
        ),
        UpgradeSchema(
            method=from__2_3_4__to__2_3_5,
            from_version="2.3.4",
            to_version="2.3.5",
        ),
        UpgradeSchema(
            method=from__2_3_5__to__2_3_6,
            from_version="2.3.5",
            to_version="2.3.6",
        ),
        UpgradeSchema(
            method=from__2_3_6__to__2_3_7,
            from_version="2.3.6",
            to_version="2.3.7",
        ),
        UpgradeSchema(
            method=from__2_3_7__to__2_3_8,
            from_version="2.3.7",
            to_version="2.3.8",
        ),
    ]

    @model_validator(mode="after")
    def validate_version(self):
        for attr in ["from_version", "to_version"]:
            versions = [getattr(x, attr) for x in self.upgrade_schemas]
            counts = Counter(versions)
            non_unique_values = [str(item) for item, count in counts.items() if count > 1]
            if len(non_unique_values) != 0:
                raise ValueError(
                    f"All {attr} in 'upgrade_schemas' should be unique. Repeated {attr} values are {non_unique_values}"
                )

        return self

    def _get_upgrade_handlers(self, from_version: str, to_version: str):
        to_version = fix_version(to_version)
        from_version = fix_version(from_version)

        upgrade_handlers = sorted(self.upgrade_schemas, key=lambda x: x.from_version)
        filtered_upgrade_handlers = list(
            filter(lambda x: x.from_version >= from_version, upgrade_handlers)
        )
        final_upgrade_handlers = list(
            filter(lambda x: x.to_version <= to_version, filtered_upgrade_handlers)
        )

        old_handler = None
        for i, handler in enumerate(final_upgrade_handlers):
            if i != 0:
                if handler.from_version != old_handler.to_version:
                    raise ValueError(
                        f"Upgrade chain is broken. Unable to find handler to upgarde from version {str(old_handler.to_version)} to {handler.from_version}"
                    )
            old_handler = handler

        if final_upgrade_handlers[0].from_version != from_version:
            raise ValueError(
                f"Upgrade chain is broken. from_version for upgrade handler should start from version {from_version}"
            )

        if final_upgrade_handlers[-1].to_version != to_version:
            raise ValueError(
                f"Upgrade chain is broken. to_version for upgrade handler should end with version {to_version}"
            )

        return final_upgrade_handlers

    def upgrade(self, data, from_version, to_version):
        handlers = self._get_upgrade_handlers(from_version, to_version)
        for handler in handlers:
            data = handler.method(data, handler.from_version, handler.to_version)
