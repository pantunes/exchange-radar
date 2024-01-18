class Validations:
    def __post_init__(self):
        for name, field in self.__dataclass_fields__.items():  # noqa
            if method := getattr(self, f"validate_{name}", None):
                setattr(self, name, method(getattr(self, name), field=field))
